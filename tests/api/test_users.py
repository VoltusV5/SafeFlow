"""Тесты для роутера пользователей."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_uow
from app.core.security import create_access_token
from app.main import app
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_get_me():
    """Тест эндпоинта GET /users/me."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    # 1. Создаем пользователя в моковой БД
    user = await mock_uow.users.create({
        "tg_id": 999111,
        "username": "testme",
        "balance": 150
    })
    
    # Создаем активную подписку
    from app.core.enums import PlanType
    from datetime import datetime, timezone, timedelta
    
    await mock_uow.subscriptions.create({
        "user_id": user.id,
        "plan": PlanType.BASE,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        "is_active": True,
        "base_device_limit": 3
    })
    
    # 2. Генерируем токен
    token = create_access_token({"sub": str(user.id)})
    
    # 3. Делаем запрос
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["user"]["telegram_id"] == 999111
    assert data["user"]["username"] == "testme"
    assert data["user"]["balance"] == 150
    assert data["active_subscription"]["plan"] == "base"
    assert data["active_subscription"]["is_active"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_me_unauthorized():
    """Тест без токена."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/users/me")
    assert response.status_code == 401
