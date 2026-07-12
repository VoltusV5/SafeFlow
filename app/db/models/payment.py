"""Модель платежа базы данных.

Модуль определяет класс Payment для хранения информации о транзакциях пользователей.  # noqa: E501
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.models.base import Base


class Payment(Base):
    """Модель платежа.

    Отслеживает статусы оплат, суммы и используемые методы платежа.

    Attributes:
        id: Внутренний идентификатор платежа.
        user_id: Идентификатор пользователя, совершившего платеж.
        gateway_payment_id: Идентификатор платежа на стороне платежного шлюза.
        amount: Сумма платежа в минимальных единицах (копейках/центах).
        currency: Валюта платежа (по умолчанию RUB).
        status: Статус платежа (например, pending, success, failed).
        payment_type: Тип платежа (например, card, crypto, balance).
        promocode: Использованный промокод (если есть).
        created_at: Дата и время создания платежа.
        user: Объект пользователя, совершившего платеж.
        promo: Объект использованного промокода.
        refund_ticket: Связанная заявка на возврат (если оформлена).
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    gateway_payment_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="RUB")
    status: Mapped[str] = mapped_column(String, nullable=False)
    payment_type: Mapped[str] = mapped_column(String, nullable=False)
    promocode: Mapped[str | None] = mapped_column(
        String, ForeignKey("promocodes.code"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # relationships
    user = relationship("User", back_populates="payments")
    promo = relationship("Promocode", back_populates="payments")
    refund_ticket = relationship(
        "RefundTicket", back_populates="payment", uselist=False
    )
