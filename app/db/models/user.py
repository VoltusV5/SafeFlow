"""Модель пользователя базы данных.

Этот модуль определяет класс User, представляющий пользователя Telegram в БД.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.models.base import Base


class User(Base):
    """Модель пользователя.

    Хранит информацию о пользователях бота, их рефералах и статусе.

    Attributes:
        id: Внутренний идентификатор пользователя.
        tg_id: Уникальный Telegram ID пользователя.
        username: Telegram username пользователя (может быть None).
        referrer_id: ID пользователя, который пригласил данного пользователя.
        trial_used: Флаг использования пробного периода.
        extra_keys: Количество дополнительных ключей, доступных пользователю.
        is_banned: Флаг блокировки пользователя.
        ref_bonus_triggered: Флаг начисления бонуса рефереру.
        created_at: Дата и время регистрации пользователя.
        referred_users: Список приглашенных пользователей (рефералов).
        subscriptions: Список подписок пользователя.
        keys: Список ключей VPN пользователя.
        payments: Список платежей пользователя.
        refund_tickets: Список заявок на возврат средств.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False
    )
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    referrer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_keys: Mapped[int] = mapped_column(Integer, default=0)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ref_bonus_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    referred_users = relationship("User", backref="referrer", remote_side=[id])
    subscriptions = relationship("Subscription", back_populates="user")
    keys = relationship("Key", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    refund_tickets = relationship("RefundTicket", back_populates="user")
