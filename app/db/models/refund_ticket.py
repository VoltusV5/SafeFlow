from sqlalchemy import BigInteger, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base

class RefundTicket(Base):
    __tablename__ = "refund_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    payment_id: Mapped[int] = mapped_column(Integer, ForeignKey("payments.id"), nullable=False)
    amount_calculated: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open")

    # relationships
    user = relationship("User", back_populates="refund_tickets")
    payment = relationship("Payment", back_populates="refund_ticket")
