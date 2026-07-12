from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.models.base import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    referrer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    trial_used: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_keys: Mapped[int] = mapped_column(Integer, default=0)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    ref_bonus_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # relationships
    referred_users = relationship("User", backref="referrer", remote_side=[id])
    subscriptions = relationship("Subscription", back_populates="user")
    keys = relationship("Key", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    refund_tickets = relationship("RefundTicket", back_populates="user")
