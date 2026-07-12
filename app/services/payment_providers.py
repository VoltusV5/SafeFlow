"""Сервисы платежных провайдеров.

Реализует паттерн Стратегия для обработки вебхуков от различных платежных систем.
Для разработки используйте SandboxProvider — локальную имитацию оплаты.
"""

import hashlib
import secrets
from abc import ABC, abstractmethod

from fastapi import Request

from app.core.config import settings


class BasePaymentProvider(ABC):
    """Абстрактный класс платежного провайдера."""

    @abstractmethod
    async def verify_signature(self, request: Request, form_data: dict) -> bool:
        """Проверяет подпись вебхука.

        Args:
            request: Объект запроса FastAPI (может понадобиться для сырого body).
            form_data: Разобранные данные формы (или JSON).

        Returns:
            True, если подпись верна, иначе False.
        """

    @abstractmethod
    def extract_order_id(self, form_data: dict) -> int:
        """Извлекает ID платежа в нашей системе.

        Args:
            form_data: Данные вебхука.

        Returns:
            ID платежа (order_id).
        """

    def create_payment_url(self, order_id: int, amount: int, description: str = "") -> str:
        """Генерирует ссылку на страницу оплаты.

        Args:
            order_id: ID платежа в нашей системе.
            amount: Сумма в копейках.
            description: Описание платежа.

        Returns:
            URL для перехода к оплате.
        """
        raise NotImplementedError("Этот провайдер не поддерживает create_payment_url")


class SandboxProvider(BasePaymentProvider):
    """Локальный провайдер для разработки и тестирования.

    Не делает реальных запросов в интернет. Имитирует полный цикл оплаты
    через встроенный FastAPI-роутер (/api/v1/payments/sandbox/*).

    Когда проект готов к проду — замените на AAIOProvider или другой провайдер.
    """

    # Секретный токен для подписи sandbox-вебхуков (защита от случайного вызова)
    _SANDBOX_SECRET = "sandbox-dev-only-secret"

    async def verify_signature(self, request: Request, form_data: dict) -> bool:
        """Проверяет подпись sandbox-вебхука.

        В sandbox просто сверяем токен из поля `sandbox_token`.
        """
        return form_data.get("sandbox_token") == self._SANDBOX_SECRET

    def extract_order_id(self, form_data: dict) -> int:
        """Извлекает order_id из данных вебхука."""
        try:
            return int(form_data.get("order_id", 0))
        except (ValueError, TypeError):
            return 0

    def create_payment_url(self, order_id: int, amount: int, description: str = "") -> str:
        """Генерирует ссылку на sandbox-страницу оплаты.

        Args:
            order_id: ID платежа.
            amount: Сумма в копейках.
            description: Описание.

        Returns:
            URL вида /api/v1/payments/sandbox/checkout/{order_id}
        """
        return f"/api/v1/payments/sandbox/checkout/{order_id}?amount={amount}"

    @classmethod
    def get_webhook_token(cls) -> str:
        """Возвращает sandbox-токен для формирования вебхука."""
        return cls._SANDBOX_SECRET


class AAIOProvider(BasePaymentProvider):
    """Провайдер для платежной системы AAIO."""

    async def verify_signature(self, request: Request, form_data: dict) -> bool:
        """Проверяет подпись AAIO.

        Формула: sign = SHA-256(merchant_id:amount:currency:secret:order_id)
        """
        merchant_id = form_data.get("merchant_id")
        amount = form_data.get("amount")
        currency = form_data.get("currency")
        order_id = form_data.get("order_id")
        sign = form_data.get("sign")

        if not all([merchant_id, amount, currency, order_id, sign]):
            return False

        secret = settings.aaio_secret_key.get_secret_value()
        sign_string = f"{merchant_id}:{amount}:{currency}:{secret}:{order_id}"
        expected_sign = hashlib.sha256(sign_string.encode("utf-8")).hexdigest()

        return sign == expected_sign

    def extract_order_id(self, form_data: dict) -> int:
        """Извлекает order_id из данных вебхука."""
        try:
            return int(form_data.get("order_id", 0))
        except (ValueError, TypeError):
            return 0

    def create_payment_url(self, order_id: int, amount: int, description: str = "") -> str:
        """Генерирует ссылку на оплату через AAIO."""
        shop_id = settings.aaio_shop_id
        amount_rub = amount / 100
        return (
            f"https://aaio.io/merchant/pay?"
            f"merchant_id={shop_id}&amount={amount_rub:.2f}"
            f"&order_id={order_id}&description={description}"
        )


def get_payment_provider() -> BasePaymentProvider:
    """Фабричный метод: возвращает нужный провайдер в зависимости от payment_mode.

    Returns:
        SandboxProvider если payment_mode == "sandbox",
        AAIOProvider если payment_mode == "production".
    """
    if settings.payment_mode == "sandbox":
        return SandboxProvider()
    return AAIOProvider()
