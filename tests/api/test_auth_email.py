import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_uow
from app.main import app
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_email_registration():
    """Тест регистрации по Email."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "password": "securepassword",
                "username": "testuser"
            }
        )
    
    print(response.json())
    assert response.status_code == 200
    data = response.json()
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
            data={
                "username": "login@example.com",
                "password": "password123"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

    app.dependency_overrides.clear()
