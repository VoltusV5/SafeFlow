"""Настройки arq Worker'а.

Определяет контекст, периодические задачи и конфигурацию для arq.
"""

import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.services.notifications import NotificationContext
from app.tasks.schedules import (delete_expired_keys,
                                 notify_expiring_subscriptions, reconcile_keys)

# Настройка логирования для воркера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def startup(ctx: dict):
    """Инициализация ресурсов при старте воркера.

    Подключаем бота и инициализируем NotificationContext.
    """
    logging.info("Starting up background worker...")

    # Инициализация бота для отправки Telegram уведомлений
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Инициализация SMTP настроек
    smtp_settings = {
        "hostname": settings.smtp_host,
        "port": settings.smtp_port,
        "username": settings.smtp_user,
        "password": settings.smtp_password,
    }

    # Создаем и кладем в контекст Стратегию уведомлений
    ctx["notification_ctx"] = NotificationContext(bot=bot, smtp_settings=smtp_settings)
    ctx["bot"] = bot
    logging.info("Worker context initialized.")


async def shutdown(ctx: dict):
    """Очистка ресурсов при остановке воркера."""
    logging.info("Shutting down background worker...")
    bot: Bot = ctx.get("bot")
    if bot:
        await bot.session.close()
    logging.info("Worker shutdown complete.")


class WorkerSettings:
    """Конфигурация arq worker'а."""

    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
    )

    on_startup = startup
    on_shutdown = shutdown

    # Регистрируем обычные функции, если они могут быть вызваны отложенно
    functions = [
        notify_expiring_subscriptions,
        delete_expired_keys,
        reconcile_keys,
    ]

    # Регистрируем периодические задачи (cron jobs)
    cron_jobs = [
        # Напоминания: каждый день в 10:00 (UTC)
        cron(notify_expiring_subscriptions, hour=10, minute=0),

        # Удаление ключей: каждый день в 02:00 (UTC)
        cron(delete_expired_keys, hour=2, minute=0),

        # Синхронизация зависших ключей: каждый час (0-я минута)
        cron(reconcile_keys, minute=0),
    ]
