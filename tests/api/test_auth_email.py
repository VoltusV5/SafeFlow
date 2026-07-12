import pytest
from httpx import ASGITransport, AsyncClient
import json

from app.api.dependencies import get_uow
from app.main import app
from tests.services.mock_uow import MockUnitOfWork

@pytest.mark.asyncio
async def test_email_registration():
    """Тест регистрации по Email (init + confirm)."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    # Мокаем Redis
    class MockRedis:
        def __init__(self):
            self.data = {}
        async def setex(self, key, ttl, value):
            self.data[key] = value
        async def get(self, key):
            return self.data.get(key)
        async def delete(self, key):
            if key in self.data:
                del self.data[key]

    mock_redis_client = MockRedis()

    from unittest.mock import AsyncMock, patch

    with patch("app.api.routes.auth.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Init registration
            response = await ac.post(
                "/api/v1/auth/register-init",
                json={
                    "email": "test@example.com",
                    "password": "securepassword"
                }
            )
            assert response.status_code == 200
            
            # Извлекаем код
            saved_data_str = mock_redis_client.data.get("reg_otp:test@example.com")
            assert saved_data_str is not None
            saved_data = json.loads(saved_data_str)
            code = saved_data["code"]

            # 2. Confirm registration
            response_confirm = await ac.post(
                "/api/v1/auth/register-confirm",
                json={
                    "email": "test@example.com",
                    "code": code
                }
            )
            assert response_confirm.status_code == 200
            data = response_confirm.json()
            assert "access_token" in data
            assert "user_id" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_email_login():
    """Тест логина по Email."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow
    
    from app.core.security import get_password_hash
    await mock_uow.users.create({
        "email": "login@example.com",
        "hashed_password": get_password_hash("password123"),
        "username": "loginuser"
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/login",
            json={
                "email": "login@example.com",
                "password": "password123"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_code_flow():
    """Тест входа по коду."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    # Создаем пользователя
    await mock_uow.users.create({
        "email": "logincode@example.com",
        "username": "logincodeuser"
    })

    class MockRedis:
        def __init__(self):
            self.data = {}
        async def setex(self, key, ttl, value):
            self.data[key] = value
        async def get(self, key):
            return self.data.get(key)
        async def delete(self, key):
            if key in self.data:
                del self.data[key]

    mock_redis_client = MockRedis()

    from unittest.mock import AsyncMock, patch

    with patch("app.api.routes.auth.get_redis", new_callable=AsyncMock) as mock_get_redis:
        mock_get_redis.return_value = mock_redis_client

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Init
            response = await ac.post(
                "/api/v1/auth/login-code-init",
                json={"email": "logincode@example.com"}
            )
            assert response.status_code == 200
            
            # Извлекаем код
            saved_code = mock_redis_client.data.get("login_otp:logincode@example.com")
            assert saved_code is not None

            # 2. Confirm
            response_good = await ac.post(
                "/api/v1/auth/login-code-confirm",
                json={"email": "logincode@example.com", "code": saved_code}
            )
            assert response_good.status_code == 200
            data = response_good.json()
            assert "access_token" in data

    app.dependency_overrides.clear()
