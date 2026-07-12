"""Тесты для сервиса пользователей (UserService)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.enums import PlanType
from app.schemas.user import UserCreate
from app.services.user_service import UserService
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_register_new_user():
    """Тест успешной регистрации нового пользователя без реферала."""
    uow = MockUnitOfWork()
    service = UserService(uow)

    user_data = UserCreate(telegram_id=123, username="test_user")
    user = await service.register_user(user_data)

    assert user.telegram_id == 123
    assert user.username == "test_user"
    assert uow.committed is True

    # Проверяем, что была создана базовая подписка (Trial)
    subs = await uow.subscriptions.get_all()
    assert len(subs) == 1
    assert subs[0].user_id == user.id
    assert subs[0].plan == PlanType.BASE


@pytest.mark.asyncio
async def test_register_existing_user():
    """Тест попытки регистрации уже существующего пользователя."""
    uow = MockUnitOfWork()
    service = UserService(uow)

    # Предварительно создаем пользователя
    await uow.users.create({"tg_id": 123, "username": "existing"})

    user_data = UserCreate(telegram_id=123, username="test_user")
    user = await service.register_user(user_data)

    # Должен вернуть существующего пользователя
    assert user.username == "existing"
    # Транзакция коммитится (ничего страшного, если просто прочитали)
    assert uow.committed is True

    # Новая подписка НЕ создаётся для существующего пользователя
    subs = await uow.subscriptions.get_all()
    assert len(subs) == 0


@pytest.mark.asyncio
async def test_register_user_with_referral():
    """Тест регистрации по реферальной ссылке с проверкой бонусных дней."""
    uow = MockUnitOfWork()
    service = UserService(uow)

    # Создаем реферера (тот, кто пригласил)
    referer = await uow.users.create({"telegram_id": 999, "username": "referer"})
    referer_base_expiry = datetime.now(timezone.utc) + timedelta(days=10)
    await uow.subscriptions.create({
        "user_id": referer.id,
        "plan": PlanType.BASE,
        "is_active": True,
        "expires_at": referer_base_expiry
    })

    user_data = UserCreate(telegram_id=123, username="referral", referred_by=referer.id)
    user = await service.register_user(user_data)

    assert user.telegram_id == 123

    # Ожидаем 10 дней (3 дня базовый триал + 7 дней бонус)
    user_subs = await uow.subscriptions.get_all()
    user_sub = next((s for s in user_subs if s.user_id == user.id), None)
    assert user_sub is not None
    assert user_sub.plan == PlanType.BASE

    min_expiry = datetime.now(timezone.utc) + timedelta(days=9)
    assert user_sub.expires_at > min_expiry, (
        f"Ожидаем срок более 9 дней, получили: {user_sub.expires_at}"
    )

    # Реферер получает +30 дней к своей подписке
    referer_sub = next((s for s in user_subs if s.user_id == referer.id), None)
    assert referer_sub is not None
    expected_referer_expiry = referer_base_expiry + timedelta(days=30)
    assert referer_sub.expires_at >= expected_referer_expiry - timedelta(seconds=5), (
        f"Реферер должен получить +30 дней, новый expires_at: {referer_sub.expires_at}"
    )


@pytest.mark.asyncio
async def test_register_user_referral_invalid_referer():
    """Тест: несуществующий реферер не блокирует регистрацию."""
    uow = MockUnitOfWork()
    service = UserService(uow)

    user_data = UserCreate(telegram_id=555, username="newuser", referred_by=99999)
    user = await service.register_user(user_data)

    # Пользователь создаётся даже если реферера нет
    assert user.telegram_id == 555
    subs = await uow.subscriptions.get_all()
    assert len(subs) == 1
    # Но без бонусных дней — только базовые 7
    user_sub = subs[0]
    max_expiry = datetime.now(timezone.utc) + timedelta(days=8)
    assert user_sub.expires_at < max_expiry
