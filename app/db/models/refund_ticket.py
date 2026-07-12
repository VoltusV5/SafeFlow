"""Модель заявки на возврат базы данных.

Модуль определяет класс RefundTicket для управления возвратами средств пользователям.  # noqa: E501
"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class RefundTicket(Base):
    """Модель заявки на возврат (тикета).

    Хранит информацию о рассчитанной сумме возврата за неиспользованное время подписки.  # noqa: E501

    Attributes:
        id: Внутренний идентификатор тикета.
        user_id: Идентификатор пользователя, запрашивающего возврат.
        payment_id: Идентификатор связанного успешного платежа.
        amount_calculated: Рассчитанная сумма к возврату (в копейках/центах).
        status: Текущий статус заявки (например, open, approved, rejected).
        user: Объект пользователя-владельца заявки.
        payment: Исходный платеж, по которому запрошен возврат.
    """

    __tablename__ = "refund_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payments.id"), nullable=False
    )
    amount_calculated: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open")

    # relationships
    user = relationship("User", back_populates="refund_tickets")
    payment = relationship("Payment", back_populates="refund_ticket")
