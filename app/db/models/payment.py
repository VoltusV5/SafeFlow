from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.models.base import Base

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    gateway_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String, default="RUB")
    status: Mapped[str] = mapped_column(String, nullable=False)
    payment_type: Mapped[str] = mapped_column(String, nullable=False)
    promocode: Mapped[str | None] = mapped_column(String, ForeignKey("promocodes.code"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    user = relationship("User", back_populates="payments")
    promo = relationship("Promocode", back_populates="payments")
    refund_ticket = relationship("RefundTicket", back_populates="payment", uselist=False)
