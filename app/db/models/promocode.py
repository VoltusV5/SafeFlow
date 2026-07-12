"""Модель промокода базы данных.

Модуль определяет класс Promocode для реализации системы скидок.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class Promocode(Base):
    """Модель промокода.

    Отслеживает доступные промокоды, их лимиты и процент скидки.

    Attributes:
        code: Строковый код (Primary Key), который вводит пользователь.
        discount_pct: Процент скидки (от 1 до 100).
        max_uses: Максимальное количество активаций.
        current_uses: Текущее количество использований промокода.
        expires_at: Дата и время истечения срока действия (может быть None).
        payments: Список платежей, в которых был использован промокод.
    """

    __tablename__ = "promocodes"

    code: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    discount_pct: Mapped[int] = mapped_column(Integer, nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    current_uses: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    payments = relationship("Payment", back_populates="promo")
