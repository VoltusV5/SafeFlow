"""Схемы (DTO) для пользователей.

Модуль определяет структуры данных для передачи информации о пользователях
между слоями приложения.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import BaseSchema


class UserCreate(BaseSchema):
    """Схема для создания нового пользователя.

    Attributes:
        telegram_id: Уникальный идентификатор пользователя в Telegram.
        username: Никнейм пользователя (если есть).
        referred_by: ID пользователя, который пригласил (если есть).
    """

    telegram_id: int
    username: Optional[str] = None
    referred_by: Optional[int] = None


class UserUpdate(BaseSchema):
    """Схема для обновления данных пользователя.

    Attributes:
        username: Никнейм пользователя.
        is_banned: Флаг блокировки.
        balance: Баланс пользователя в минимальных единицах.
    """

    username: Optional[str] = None
    is_banned: Optional[bool] = None
    balance: Optional[int] = Field(None, ge=0)


class UserResponse(BaseSchema):
    """Схема для возврата данных пользователя.

    Attributes:
        id: Внутренний ID.
        telegram_id: Telegram ID.
        username: Никнейм.
        balance: Текущий баланс.
        is_banned: Статус блокировки.
        created_at: Дата регистрации.
    """

    id: int
    telegram_id: int
    username: Optional[str] = None
    balance: int
    is_banned: bool
    created_at: datetime
