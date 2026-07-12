"""Сервис уведомлений.

Реализует паттерн "Стратегия" для отправки уведомлений пользователям
(Telegram или Email).
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict

from aiogram import Bot


class BaseNotificationStrategy(ABC):
    """Базовый интерфейс для отправки уведомлений."""

    @abstractmethod
    async def send(self, user_id: int, message: str, **kwargs) -> bool:
        """Отправляет уведомление пользователю.

        Args:
            user_id: Идентификатор пользователя в БД.
            message: Текст сообщения.

        Returns:
            True, если отправлено успешно.
        """
        pass


class TelegramNotificationStrategy(BaseNotificationStrategy):
    """Стратегия отправки через Telegram."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send(self, user_id: int, message: str, **kwargs) -> bool:
        tg_id = kwargs.get("tg_id")
        if not tg_id:
            logging.error(
                f"Cannot send TG message to user {user_id}: no tg_id provided.")
            return False

        try:
            await self.bot.send_message(chat_id=tg_id, text=message)
            return True
        except Exception as e:
            logging.error(f"Failed to send TG message to {tg_id}: {e}")
            return False


class EmailNotificationStrategy(BaseNotificationStrategy):
    """Стратегия отправки через Email (пока mock)."""

    def __init__(self, smtp_settings: dict):
        self.smtp_settings = smtp_settings

    async def send(self, user_id: int, message: str, **kwargs) -> bool:
        email = kwargs.get("email")
        if not email:
            logging.error(f"Cannot send Email to user {user_id}: no email provided.")
            return False

        # TODO: Реализовать реальную отправку через aiosmtplib
        logging.info(f"[MOCK EMAIL] To: {email} | Message: {message}")
        return True


class NotificationContext:
    """Контекст для выбора нужной стратегии уведомления."""

    def __init__(self, bot: Bot = None, smtp_settings: dict = None):
        self.strategies: Dict[str, BaseNotificationStrategy] = {
            "telegram": TelegramNotificationStrategy(bot) if bot else None,
            "email": EmailNotificationStrategy(smtp_settings)
            if smtp_settings else EmailNotificationStrategy({}),
        }

    async def notify(self, user, message: str) -> bool:
        """Определяет предпочтение пользователя и отправляет уведомление.

        Args:
            user: Объект модели User или Pydantic DTO (должен иметь поля
                  notification_preference, tg_id, email).
            message: Текст уведомления.

        Returns:
            True при успешной отправке.
        """
        preference = getattr(user, "notification_preference", "telegram")
        strategy = self.strategies.get(preference)

        if not strategy:
            logging.error(f"No strategy found for preference {preference}")
            return False

        return await strategy.send(
            user_id=getattr(user, "id", 0),
            message=message,
            tg_id=getattr(user, "tg_id", None) or getattr(user, "telegram_id", None),
            email=getattr(user, "email", None)
        )
