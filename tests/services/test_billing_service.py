"""Тесты для сервиса биллинга (BillingService)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.enums import (PaymentStatus, PaymentType, PlanType,
                            RefundTicketStatus)
from app.schemas.billing import PaymentCreate
from app.services.billing_service import BillingService
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_process_new_subscription():
    """Тест оформления новой подписки (BASE → PREMIUM)."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    user = await uow.users.create({"telegram_id": 123, "balance": 0})
    await uow.subscriptions.create({
        "user_id": user.id,
        "plan": PlanType.BASE,
        "is_active": True,
        "expires_at": datetime.now(timezone.utc)
    })

    payment_data = PaymentCreate(
        user_id=user.id,
        amount=50000,
        payment_type=PaymentType.NEW_SUB,
        status=PaymentStatus.SUCCESS
    )

    result_sub = await service.process_payment(payment_data)

    assert result_sub.plan == PlanType.PREMIUM
    assert result_sub.is_active is True
    assert uow.committed is True


@pytest.mark.asyncio
async def test_process_payment_extends_active_subscription():
    """Тест продления уже активной подписки (срок суммируется)."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    user = await uow.users.create({"telegram_id": 456, "balance": 0})
    future_expiry = datetime.now(timezone.utc) + timedelta(days=15)
    await uow.subscriptions.create({
        "user_id": user.id,
        "plan": PlanType.PREMIUM,
        "is_active": True,
        "expires_at": future_expiry
    })

    payment_data = PaymentCreate(
        user_id=user.id,
        amount=50000,
        payment_type=PaymentType.RENEWAL,
        status=PaymentStatus.SUCCESS
    )

    result_sub = await service.process_payment(payment_data)

    # Ожидаем: future_expiry + 30 дней (не от сегодня, а от текущего expires_at)
    expected_min = future_expiry + timedelta(days=29)  # небольшой запас
    assert result_sub.expires_at > expected_min
    assert result_sub.plan == PlanType.PREMIUM


@pytest.mark.asyncio
async def test_process_payment_failed_status_rejected():
    """Тест: платёж с нежелательным статусом должен быть отклонён до создания в БД."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    user = await uow.users.create({"telegram_id": 789})

    payment_data = PaymentCreate(
        user_id=user.id,
        amount=50000,
        payment_type=PaymentType.NEW_SUB,
        status=PaymentStatus.FAILED
    )

    with pytest.raises(ValueError, match="Payment is not successful"):
        await service.process_payment(payment_data)

    # Платёж НЕ должен быть сохранён в БД (проверка до create)
    all_payments = await uow.payments.get_all()
    assert len(all_payments) == 0


@pytest.mark.asyncio
async def test_complete_payment_success():
    """Тест успешного завершения PENDING платежа по вебхуку."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    user = await uow.users.create({"telegram_id": 111})
    payment = await uow.payments.create({
        "user_id": user.id,
        "amount": 50000,
        "status": PaymentStatus.PENDING,
        "payment_type": PaymentType.NEW_SUB
    })

    result_sub = await service.complete_payment(payment.id)

    assert result_sub.plan == PlanType.PREMIUM
    assert result_sub.is_active is True
    assert uow.committed is True

    # Статус платежа должен смениться на PAID
    updated_payment = await uow.payments.get(payment.id)
    assert updated_payment.status == PaymentStatus.PAID


@pytest.mark.asyncio
async def test_complete_payment_not_found():
    """Тест: complete_payment бросает ValueError если платёж не найден."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    with pytest.raises(ValueError, match="Payment not found"):
        await service.complete_payment(999)


@pytest.mark.asyncio
async def test_complete_payment_already_paid():
    """Тест: complete_payment бросает ValueError если платёж уже PAID (идемпотентность)."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    user = await uow.users.create({"telegram_id": 222})
    payment = await uow.payments.create({
        "user_id": user.id,
        "amount": 50000,
        "status": PaymentStatus.PAID,
        "payment_type": PaymentType.NEW_SUB
    })

    with pytest.raises(ValueError, match="already processed"):
        await service.complete_payment(payment.id)


@pytest.mark.asyncio
async def test_apply_promocode():
    """Тест применения промокода."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    await uow.promocodes.create({
        "code": "TEST50",
        "discount_percent": 50,
        "is_active": True,
        "used_count": 0
    })

    amount_to_pay = await service.calculate_amount_with_promo(50000, "TEST50")

    assert amount_to_pay == 25000  # 50% скидка


@pytest.mark.asyncio
async def test_apply_unknown_promocode_no_effect():
    """Тест: неизвестный промокод не изменяет сумму."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    amount = await service.calculate_amount_with_promo(50000, "NONEXISTENT")
    assert amount == 50000


@pytest.mark.asyncio
async def test_create_refund():
    """Тест создания заявки на возврат."""
    uow = MockUnitOfWork()
    service = BillingService(uow)

    user = await uow.users.create({"telegram_id": 123})
    payment = await uow.payments.create({
        "user_id": user.id,
        "amount": 50000,
        "status": PaymentStatus.SUCCESS,
        "payment_type": PaymentType.NEW_SUB
    })

    ticket = await service.create_refund_ticket(user.id, payment.id, 25000)

    assert ticket.amount_calculated == 25000
    assert ticket.status == RefundTicketStatus.OPEN
    assert uow.committed is True
