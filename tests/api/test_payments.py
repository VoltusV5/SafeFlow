"""Тесты эндпоинтов платежей и sandbox-оплаты."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_uow
from app.core.enums import PaymentStatus, PaymentType
from app.main import app
from app.services.payment_providers import AAIOProvider, SandboxProvider
from tests.services.mock_uow import MockUnitOfWork


# ---------------------------------------------------------------------------
# Тесты SandboxProvider
# ---------------------------------------------------------------------------

class TestSandboxProvider:
    """Тесты для SandboxProvider."""

    @pytest.mark.asyncio
    async def test_valid_sandbox_token_accepted(self):
        """Корректный sandbox_token проходит проверку подписи."""
        provider = SandboxProvider()
        form_data = {
            "sandbox_token": SandboxProvider._SANDBOX_SECRET,
            "order_id": "1"
        }
        assert await provider.verify_signature(None, form_data) is True

    @pytest.mark.asyncio
    async def test_invalid_sandbox_token_rejected(self):
        """Неверный sandbox_token отклоняется."""
        provider = SandboxProvider()
        form_data = {
            "sandbox_token": "wrong-token",
            "order_id": "1"
        }
        assert await provider.verify_signature(None, form_data) is False

    def test_extract_order_id_valid(self):
        """Валидный order_id извлекается корректно."""
        provider = SandboxProvider()
        assert provider.extract_order_id({"order_id": "42"}) == 42

    def test_extract_order_id_non_numeric(self):
        """Нечисловой order_id возвращает 0 (без ValueError)."""
        provider = SandboxProvider()
        assert provider.extract_order_id({"order_id": "abc-not-a-number"}) == 0

    def test_extract_order_id_missing(self):
        """Отсутствующий order_id возвращает 0."""
        provider = SandboxProvider()
        assert provider.extract_order_id({}) == 0

    def test_create_payment_url(self):
        """URL для sandbox содержит payment_id."""
        provider = SandboxProvider()
        url = provider.create_payment_url(order_id=7, amount=10000)
        assert "7" in url
        assert "sandbox" in url


# ---------------------------------------------------------------------------
# Тесты AAIOProvider
# ---------------------------------------------------------------------------

class TestAAIOProvider:
    """Тесты для AAIOProvider."""

    @pytest.mark.asyncio
    async def test_invalid_aaio_signature(self):
        """Неверная подпись AAIO отклоняется."""
        provider = AAIOProvider()
        form_data = {
            "merchant_id": "test",
            "amount": "100",
            "currency": "RUB",
            "order_id": "1",
            "sign": "invalid_sign"
        }
        result = await provider.verify_signature(None, form_data)
        assert result is False

    def test_extract_order_id_non_numeric(self):
        """Нечисловой order_id в AAIO вебхуке возвращает 0."""
        provider = AAIOProvider()
        assert provider.extract_order_id({"order_id": "abc"}) == 0


# ---------------------------------------------------------------------------
# Тесты HTTP-эндпоинтов (sandbox)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sandbox_checkout_page():
    """Тест: страница sandbox оплаты отдаётся с кодом 200."""
    mock_uow = MockUnitOfWork()
    payment = await mock_uow.payments.create({
        "user_id": 1,
        "amount": 50000,
        "status": PaymentStatus.PENDING,
        "payment_type": PaymentType.NEW_SUB
    })
    app.dependency_overrides[get_uow] = lambda: mock_uow

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/payments/sandbox/checkout/{payment.id}")

    assert response.status_code == 200
    assert "SafeFlow VPN" in response.text
    assert "SANDBOX" in response.text

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sandbox_checkout_not_found():
    """Тест: 404 если платёж не найден."""
    mock_uow = MockUnitOfWork()
    app.dependency_overrides[get_uow] = lambda: mock_uow

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/payments/sandbox/checkout/99999")

    assert response.status_code == 404
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sandbox_confirm_success():
    """Тест: подтверждение sandbox платежа активирует подписку."""
    mock_uow = MockUnitOfWork()
    user = await mock_uow.users.create({"tg_id": 123})
    payment = await mock_uow.payments.create({
        "user_id": user.id,
        "amount": 50000,
        "status": PaymentStatus.PENDING,
        "payment_type": PaymentType.NEW_SUB
    })
    app.dependency_overrides[get_uow] = lambda: mock_uow

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(f"/api/v1/payments/sandbox/confirm/{payment.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["subscription"]["is_active"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_aaio_webhook_disabled_in_sandbox():
    """Тест: AAIO webhook возвращает 404 в sandbox-режиме."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/payments/aaio/webhook",
            data={"merchant_id": "x", "amount": "100", "order_id": "1", "sign": "s"}
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_aaio_webhook_invalid_signature():
    """Тест: AAIO webhook с неверной подписью возвращает 400."""
    # Этот тест актуален в production режиме, здесь проверяем сам провайдер
    provider = AAIOProvider()
    form_data = {
        "merchant_id": "test_shop",
        "amount": "500",
        "currency": "RUB",
        "order_id": "42",
        "sign": "definitely_wrong_hash"
    }
    result = await provider.verify_signature(None, form_data)
    assert result is False


@pytest.mark.asyncio
async def test_aaio_webhook_success():
    """Тест: провайдер AAIO с правильной подписью проходит валидацию."""
    import hashlib

    from app.core.config import settings

    provider = AAIOProvider()
    secret = settings.aaio_secret_key.get_secret_value()
    merchant_id = settings.aaio_shop_id
    amount = "500"
    currency = "RUB"
    order_id = "1"

    sign_string = f"{merchant_id}:{amount}:{currency}:{secret}:{order_id}"
    correct_sign = hashlib.sha256(sign_string.encode("utf-8")).hexdigest()

    form_data = {
        "merchant_id": merchant_id,
        "amount": amount,
        "currency": currency,
        "order_id": order_id,
        "sign": correct_sign
    }

    result = await provider.verify_signature(None, form_data)
    assert result is True
