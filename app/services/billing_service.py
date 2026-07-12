"""Сервис бизнес-логики биллинга.

Модуль определяет класс BillingService для обработки подписок,
платежей, промокодов и возвратов.
"""

from datetime import datetime, timedelta, timezone

from app.core.enums import PaymentStatus, PlanType, RefundTicketStatus
from app.db.uow import UnitOfWork
from app.schemas.billing import (PaymentCreate, RefundTicketResponse,
                                 SubscriptionResponse)


class BillingService:
    """Сервис для работы с биллингом."""

    def __init__(self, uow: UnitOfWork):
        """Инициализация сервиса.

        Args:
            uow: Интерфейс Unit of Work для работы с БД.
        """
        self.uow = uow

    async def calculate_amount_with_promo(self, amount: int, promocode_str: str | None) -> int:
        """Расчет итоговой суммы с учетом промокода.

        Args:
            amount: Исходная сумма в копейках.
            promocode_str: Строка промокода (может быть None).

        Returns:
            Итоговая сумма к оплате.
        """
        if not promocode_str:
            return amount

        async with self.uow:
            all_promos = await self.uow.promocodes.get_all()
            promo = next(
                (p for p in all_promos if getattr(p, "code", None)
                 == promocode_str and getattr(p, "is_active", False)),
                None
            )

            if promo:
                discount = getattr(promo, "discount_percent", 0)
                amount = int(amount * (100 - discount) / 100)

        return max(amount, 0)

    async def _activate_subscription(self, user_id: int) -> SubscriptionResponse:
        """Активирует или продлевает подписку пользователя на 30 дней.

        Вызывается внутри активной UoW-сессии.

        Args:
            user_id: ID пользователя.

        Returns:
            DTO с данными обновлённой подписки.
        """
        all_subs = await self.uow.subscriptions.get_all()
        sub = next(
            (s for s in all_subs if getattr(s, "user_id", None) == user_id),
            None
        )

        now = datetime.now(timezone.utc)
        new_expiry = now + timedelta(days=30)

        if sub:
            # Если подписка ещё активна — продлеваем от текущего expires_at
            current_expiry = getattr(sub, "expires_at", now)
            if current_expiry and current_expiry > now:
                new_expiry = current_expiry + timedelta(days=30)

            updated_sub = await self.uow.subscriptions.update(
                sub,
                {
                    "plan": PlanType.PREMIUM,
                    "expires_at": new_expiry,
                    "is_active": True
                }
            )
        else:
            updated_sub = await self.uow.subscriptions.create(
                {
                    "user_id": user_id,
                    "plan": PlanType.PREMIUM,
                    "expires_at": new_expiry,
                    "is_active": True,
                    "base_device_limit": 5
                }
            )

        return SubscriptionResponse.model_validate(
            {
                "id": getattr(updated_sub, "id", 1),
                "user_id": user_id,
                "plan": getattr(updated_sub, "plan", PlanType.PREMIUM),
                "expires_at": getattr(updated_sub, "expires_at", new_expiry),
                "base_device_limit": getattr(updated_sub, "base_device_limit", 5),
                "is_active": getattr(updated_sub, "is_active", True)
            }
        )

    async def process_payment(self, payment_in: PaymentCreate) -> SubscriptionResponse:
        """Обработка успешного платежа и активация подписки.

        Args:
            payment_in: Данные платежа.

        Returns:
            Обновленные данные подписки.

        Raises:
            ValueError: Если статус платежа не SUCCESS.
        """
        # Сначала проверяем статус — до записи в БД
        if payment_in.status != PaymentStatus.SUCCESS:
            raise ValueError("Payment is not successful")

        async with self.uow:
            # 1. Сохраняем платеж
            await self.uow.payments.create(payment_in.model_dump())

            # 2. Обновляем счётчик промокода (если есть)
            if payment_in.promocode:
                all_promos = await self.uow.promocodes.get_all()
                promo = next(
                    (p for p in all_promos if getattr(
                        p, "code", None) == payment_in.promocode),
                    None
                )
                if promo:
                    used = getattr(promo, "used_count", 0)
                    await self.uow.promocodes.update(promo, {"used_count": used + 1})

            # 3. Активируем подписку (выделено в отдельный метод)
            return await self._activate_subscription(payment_in.user_id)

    async def complete_payment(self, payment_id: int) -> SubscriptionResponse:
        """Завершает существующий PENDING платёж (например, по вебхуку) и выдаёт подписку.

        Args:
            payment_id: ID платежа в нашей БД.

        Returns:
            DTO с данными обновлённой подписки.

        Raises:
            ValueError: Если платёж не найден или не в статусе PENDING.
        """
        async with self.uow:
            payment = await self.uow.payments.get(payment_id)
            if not payment:
                raise ValueError("Payment not found")

            if payment.status == PaymentStatus.PAID:
                raise ValueError("Payment already processed")

            if payment.status != PaymentStatus.PENDING:
                raise ValueError(
                    f"Cannot complete payment in status '{payment.status}'"
                )

            await self.uow.payments.update(payment, {"status": PaymentStatus.PAID})

            return await self._activate_subscription(payment.user_id)

    async def create_refund_ticket(
        self, user_id: int, payment_id: int, amount: int
    ) -> RefundTicketResponse:
        """Создание заявки на возврат.

        Args:
            user_id: ID пользователя.
            payment_id: ID платежа.
            amount: Рассчитанная сумма к возврату.

        Returns:
            Созданная заявка на возврат.
        """
        async with self.uow:
            ticket = await self.uow.refund_tickets.create(
                {
                    "user_id": user_id,
                    "payment_id": payment_id,
                    "amount_calculated": amount,
                    "status": RefundTicketStatus.OPEN
                }
            )

            return RefundTicketResponse.model_validate(
                {
                    "id": getattr(ticket, "id", 1),
                    "user_id": user_id,
                    "payment_id": payment_id,
                    "amount_calculated": amount,
                    "status": getattr(ticket, "status", RefundTicketStatus.OPEN)
                }
            )
