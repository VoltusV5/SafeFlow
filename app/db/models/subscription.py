"""Модель подписки базы данных.

Модуль определяет класс Subscription для управления подписками пользователей.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class Subscription(Base):
    """Модель подписки пользователя.

    Хранит информацию о тарифном плане, сроке действия и лимитах пользователя.

    Attributes:
        id: Внутренний идентификатор подписки.
        user_id: Идентификатор пользователя (внешний ключ).
        plan: Название тарифного плана.
        expires_at: Дата и время окончания действия подписки.
        base_device_limit: Базовый лимит устройств для этой подписки.
        is_active: Флаг активности подписки.
        user: Объект пользователя, которому принадлежит подписка.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    base_device_limit: Mapped[int] = mapped_column(Integer, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # relationships
    user = relationship("User", back_populates="subscriptions")
