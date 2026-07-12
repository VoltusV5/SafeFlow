"""Задачи и расписания (Cron Jobs) для arq.

Модуль определяет функции-задачи для выполнения в фоне.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import Subscription, User
from app.db.uow import UnitOfWork
from app.services.notifications import NotificationContext
from app.services.vpn_client import VPNClientService


async def notify_expiring_subscriptions(ctx: dict):
    """Напоминает пользователям об истечении подписки (за 3 дня).

    Функция запускается периодически и находит активные подписки,
    которые истекают через 3 дня.

    Args:
        ctx: Контекст задачи arq.
    """
    logging.info("Running task: notify_expiring_subscriptions")
    notification_ctx: NotificationContext = ctx.get("notification_ctx")

    if not notification_ctx:
        logging.error("NotificationContext not found in worker context")
        return

    # Запускаем раз в сутки. Ищем подписки, истекающие от 3 до 4 дней
    # (уведомление за 3 дня) и от 1 до 2 дней (уведомление за 24 часа).
    now = datetime.now(timezone.utc)
    target_3_start = now + timedelta(days=3)
    target_3_end = now + timedelta(days=4)

    target_1_start = now + timedelta(days=1)
    target_1_end = now + timedelta(days=2)

    async with UnitOfWork() as uow:
        stmt = (
            select(Subscription, User)
            .join(User, Subscription.user_id == User.id)
            .filter(
                Subscription.is_active,
                (
                    (Subscription.expires_at >= target_3_start)
                    & (Subscription.expires_at < target_3_end)
                ) | (
                    (Subscription.expires_at >= target_1_start)
                    & (Subscription.expires_at < target_1_end)
                )
            )
        )

        result = await uow.session.execute(stmt)
        rows = result.all()

        count = 0
        for sub, user in rows:
            # sub.expires_at в диапазоне [now+1d, now+2d) → уведомление за 24 часа
            # sub.expires_at в диапазоне [now+3d, now+4d) → уведомление за 3 дня
            if sub.expires_at < target_3_start:
                message = (
                    "⏳ Ваша подписка на VPN истекает менее чем через 24 часа! "
                    "Пожалуйста, пополните баланс и продлите её."
                )
            else:
                message = (
                    "⚠️ Ваша подписка на VPN истекает через 3 дня! "
                    "Пожалуйста, пополните баланс и продлите её."
                )

            success = await notification_ctx.notify(user, message)
            if success:
                count += 1

        logging.info(f"Notified {count} users about expiring subscriptions.")


async def delete_expired_keys(ctx: dict):
    """Удаляет ключи, если подписка истекла и прошел Grace Period (24 часа).

    Args:
        ctx: Контекст задачи arq.
    """
    logging.info("Running task: delete_expired_keys")
    now = datetime.now(timezone.utc)
    grace_period_end = now - timedelta(hours=24)

    async with UnitOfWork() as uow:
        # TODO: Реализовать логику удаления ключей из 3x-ui / xray.
        # Пока просто делаем выборку и логируем.
        stmt = (
            select(User)
            .join(Subscription, User.id == Subscription.user_id, isouter=True)
            .filter(
                (Subscription.is_active.is_(False))
                | (Subscription.expires_at < grace_period_end)
                | (Subscription.id.is_(None))
            )
        )
        result = await uow.session.execute(stmt)
        users = result.scalars().all()

        # Для каждого такого пользователя надо найти активные ключи и удалить их
        vpn_client = VPNClientService()
        for user in users:
            logging.info(
                f"User {user.id} subscription expired or missing. "
                "Keys should be deleted."
            )

            user_keys = await uow.keys.get_active_by_user_id(user.id)
            for key in user_keys:
                server = await uow.servers.get(key.server_id)
                server_ip = getattr(
                    server,
                    "ip_address",
                    "127.0.0.1") if server else "127.0.0.1"
                client_id = key.client_uuid or key.internal_ip

                if client_id:
                    success = await vpn_client.delete_key(server_ip, client_id)
                    if success:
                        await uow.keys.update(key, {"status": "revoked"})

        # Не забываем закоммитить изменения статусов ключей
        await uow.commit()


async def reconcile_keys(ctx: dict):
    """Синхронизирует ключи в статусе pending_sync с серверами.

    Args:
        ctx: Контекст задачи arq.
    """
    logging.info("Running task: reconcile_keys")

    async with UnitOfWork() as uow:
        vpn_client = VPNClientService()
        # Ищем ключи в статусе pending_sync
        all_keys = await uow.keys.get_all()
        pending_keys = [
            k for k in all_keys if getattr(
                k, "status", None) == "pending_sync"]

        for key in pending_keys:
            server = await uow.servers.get(key.server_id)
            server_ip = getattr(
                server,
                "ip_address",
                "127.0.0.1") if server else "127.0.0.1"
            client_id = key.client_uuid or key.internal_ip

            if client_id:
                success = await vpn_client.sync_key(server_ip, client_id, "active")
                if success:
                    await uow.keys.update(key, {"status": "active"})

        await uow.commit()
