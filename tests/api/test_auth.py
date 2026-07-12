"""Тесты эндпоинтов авторизации."""

import hashlib
import hmac
import json
import time
import urllib.parse

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_uow
from app.api.routes.auth import verify_telegram_data
from app.core.config import settings
from app.main import app
from tests.services.mock_uow import MockUnitOfWork


def _make_init_data(user_data: dict, bot_token: str, auth_date: int = None) -> str:
    """Генерирует валидную строку initData с правильной подписью HMAC.

    Args:
        user_data: Данные пользователя (dict).
        bot_token: Токен бота для подписи.
        auth_date: Unix timestamp (по умолчанию — текущее время).

    Returns:
        URL-encoded строка initData с полем hash.
    """
    if auth_date is None:
        auth_date = int(time.time())

    data_dict = {
        "query_id": "mock",
        "user": json.dumps(user_data, separators=(",", ":")),
        "auth_date": str(auth_date)
    }

    sorted_keys = sorted(data_dict.keys())
    data_check_string = "\n".join(f"{k}={data_dict[k]}" for k in sorted_keys)

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    return urllib.parse.urlencode(data_dict) + f"&hash={calculated_hash}"


# ---------------------------------------------------------------------------
# Тесты функции verify_telegram_data
# ---------------------------------------------------------------------------

class TestVerifyTelegramData:
    """Тесты функции валидации initData от Telegram."""

    def test_valid_data_returns_user(self):
        """Корректные данные с актуальным auth_date возвращают dict пользователя."""
        bot_token = settings.bot_token.get_secret_value()
        user = {"id": 123456, "first_name": "Test"}
        init_data = _make_init_data(user, bot_token)

        result = verify_telegram_data(init_data, bot_token)

        assert result is not None
        assert result["id"] == 123456
        assert result["first_name"] == "Test"

    def test_invalid_hash_returns_none(self):
        """Неверная подпись (hash) → None."""
        bot_token = settings.bot_token.get_secret_value()
        user = {"id": 123456, "first_name": "Test"}
        init_data = _make_init_data(user, bot_token)

        # Подменяем hash
        tampered = init_data.replace(
            init_data.split("hash=")[1], "deadbeef1234567890"
        )

        result = verify_telegram_data(tampered, bot_token)
        assert result is None

    def test_expired_auth_date_returns_none(self):
        """Просроченный auth_date (старше 24ч) → None (защита от replay-атак)."""
        bot_token = settings.bot_token.get_secret_value()
        user = {"id": 123456, "first_name": "Test"}
        old_timestamp = int(time.time()) - 90000  # 25 часов назад

        init_data = _make_init_data(user, bot_token, auth_date=old_timestamp)

        result = verify_telegram_data(init_data, bot_token)
        assert result is None

    def test_missing_hash_returns_none(self):
        """Отсутствие поля hash → None."""
        init_data = "query_id=mock&user=%7B%22id%22%3A1%7D"

        result = verify_telegram_data(init_data, "any_token")
        assert result is None

    def test_wrong_bot_token_returns_none(self):
        """Данные, подписанные другим токеном бота, не валидируются."""
        real_token = settings.bot_token.get_secret_value()
        wrong_token = "0000000:wrong_token"
        user = {"id": 123456, "first_name": "Test"}
        init_data = _make_init_data(user, real_token)

        result = verify_telegram_data(init_data, wrong_token)
        assert result is None

    def test_recent_auth_date_passes(self):
        """auth_date только что созданный (несколько секунд назад) — проходит."""
        bot_token = settings.bot_token.get_secret_value()
        user = {"id": 999, "first_name": "Fresh"}
        # 1 секунду назад — должен пройти
        init_data = _make_init_data(user, bot_token, auth_date=int(time.time()) - 1)

        result = verify_telegram_data(init_data, bot_token)
        assert result is not None


# ---------------------------------------------------------------------------
# Тесты HTTP-эндпоинтов авторизации
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_telegram_login():
    """Тест авторизации через Telegram (TWA) — успешный кейс."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    bot_token = settings.bot_token.get_secret_value()
    user = {"id": 123456, "first_name": "Test"}
    init_data = _make_init_data(user, bot_token)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/telegram",
            json={"initData": init_data}
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_auth_telegram_invalid_hash():
    """Тест: запрос с неверным hash возвращает 400."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/auth/telegram",
            json={"initData": "query_id=mock&user=%7B%22id%22%3A1%7D&hash=badhash"}
        )

    assert response.status_code == 400
    app.dependency_overrides.clear()



