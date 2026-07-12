"""Схемы (DTO) для пользователей.

Модуль определяет структуры данных для передачи информации о пользователях
между слоями приложения.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field, BaseModel, EmailStr

from app.schemas.base import BaseSchema


class UserCreate(BaseModel):
    telegram_id: int | None = Field(default=None, description="Telegram ID пользователя")
    email: str | None = Field(default=None, description="Email пользователя")
    password: str | None = Field(default=None, description="Пароль пользователя (для Email-регистрации)")
    username: str | None = Field(default=None, description="Имя пользователя в Telegram")
    referred_by: int | None = Field(default=None, description="ID реферера")


class UserEmailLogin(BaseSchema):
    email: EmailStr
    password: str

class RegisterInitRequest(BaseSchema):
    email: EmailStr
    password: str

class RegisterConfirmRequest(BaseSchema):
    email: EmailStr
    code: str

class LoginCodeInitRequest(BaseSchema):
    email: EmailStr

class LoginCodeConfirmRequest(BaseSchema):
    email: EmailStr
    code: str


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
    telegram_id: int | None = None
    username: str | None = None
    email: str | None = None
    balance: float
    is_banned: bool
    created_at: datetime


class SubscriptionInfo(BaseSchema):
    """Схема информации об активной подписке для TWA."""
    plan: str
    expires_at: Optional[datetime] = None
    is_active: bool


class UserMeResponse(BaseSchema):
    """Схема ответа для эндпоинта /users/me."""
    user: UserResponse
    active_subscription: Optional[SubscriptionInfo] = None
