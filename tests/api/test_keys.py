"""Тесты эндпоинтов для управления ключами через REST API."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_uow
from app.core.enums import KeyStatus, Protocol
from app.core.security import create_access_token
from app.main import app
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_get_my_keys_unauthorized():
    """Тест получения ключей без токена."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/keys/my")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_my_keys_success(async_session):
    """Тест успешного получения ключей пользователя."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    # Создаем пользователя
    user = await mock_uow.users.create({"tg_id": 1111})

    # Создаем ключ
    from datetime import datetime, timedelta, timezone
    key = await mock_uow.keys.create({
        "user_id": user.id,
        "server_id": 1,
        "protocol": Protocol.AWG,
        "internal_ip": "10.8.0.2",
        "client_uuid": "mock-uuid-1234",
        "config_data": "mock_config_data_string",
        "status": KeyStatus.ACTIVE,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30)
    })

    token = create_access_token(data={"sub": str(user.id)})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/keys/my",
            headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["internal_ip"] == "10.8.0.2"

    app.dependency_overrides.clear()
