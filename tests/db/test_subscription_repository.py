"""Тесты репозитория подписок.

Модуль проверяет методы получения активных подписок.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.db.repositories.subscription import SubscriptionRepository
from app.db.repositories.user import UserRepository


@pytest.mark.asyncio
async def test_subscription_repository_get_active(async_session):
    """Тест поиска активной подписки пользователя.

    Проверяет, что метод возвращает подписку только если is_active=True.

    Args:
        async_session: Фикстура асинхронной сессии БД.
    """
    user_repo = UserRepository(async_session)
    sub_repo = SubscriptionRepository(async_session)

    user = await user_repo.create({"tg_id": 111, "username": "sub_user"})

    # Active sub
    future_date = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=30
    )
    sub = await sub_repo.create(
        {
            "user_id": user.id,
            "plan": "1_month",
            "expires_at": future_date,
            "is_active": True,
        }
    )

    active_sub = await sub_repo.get_active_by_user_id(user.id)
    assert active_sub is not None
    assert active_sub.id == sub.id

    # Update to inactive
    await sub_repo.update(sub, {"is_active": False})

    active_sub_none = await sub_repo.get_active_by_user_id(user.id)
    assert active_sub_none is None
