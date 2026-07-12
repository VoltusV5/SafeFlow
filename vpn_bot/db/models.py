from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vpn_bot.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger(), unique=True, index=True)
    tg_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_banned: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="0"
    )  # noqa: E501
    password_entered: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="0"
    )
    password_fail_attempts: Mapped[int] = mapped_column(
        Integer(), default=0, server_default="0"
    )
    # Колонка в SQLite исторически называется trial_start_date; на ключи VPN не влияет.  # noqa: E501
    first_password_ok_at: Mapped[datetime | None] = mapped_column(
        "trial_start_date",
        DateTime(timezone=True),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    keys: Mapped[list[VpnKey]] = relationship(back_populates="user")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user"
    )  # noqa: E501
    star_donation_sub: Mapped[StarDonationSubscription | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    da_donation_sub: Mapped["DonationAlertsSubscription | None"] = (
        relationship(  # noqa: E501
            back_populates="user",
            uselist=False,
        )
    )
    star_payments: Mapped[list[StarPayment]] = relationship(
        back_populates="user"
    )  # noqa: E501
    bandwidth_limit: Mapped[UserLimit | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    support_funnel_events: Mapped[list["SupportFunnelEvent"]] = relationship(
        back_populates="user",
    )


class SupportFunnelEvent(Base):
    """События воронки «Поддержать» (кнопки и шаги внутри бота)."""

    __tablename__ = "support_funnel_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    event: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    user: Mapped[User] = relationship(back_populates="support_funnel_events")


class VpnKey(Base):
    __tablename__ = "vpn_keys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )  # noqa: E501
    protocol: Mapped[str] = mapped_column(String(64), index=True)
    config_filename: Mapped[str] = mapped_column(
        String(255), default="config.txt"
    )  # noqa: E501
    key_value: Mapped[str] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="1"
    )  # noqa: E501
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    regenerated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # noqa: E501
    wg_peer_public_key: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # noqa: E501
    custom_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="keys")


class UserLimit(Base):
    __tablename__ = "user_limits"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    limit_mbps: Mapped[int] = mapped_column(
        Integer(), default=500, server_default="500"
    )  # noqa: E501
    fair_share_active: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="bandwidth_limit")


class DonationAlertsSubscription(Base):
    """Ежемесячное напоминание открыть Donation Alerts (оплата на стороне сайта)."""  # noqa: E501

    __tablename__ = "donation_alerts_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    next_reminder_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="1"
    )  # noqa: E501
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="da_donation_sub")


class StarDonationSubscription(Base):
    __tablename__ = "star_donation_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    stars_amount: Mapped[int] = mapped_column(Integer())
    next_reminder_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="1"
    )  # noqa: E501
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="star_donation_sub")


class StarPayment(Base):
    __tablename__ = "star_payments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    stars_amount: Mapped[int] = mapped_column(Integer())
    monthly_pledge: Mapped[bool] = mapped_column(
        Boolean(), default=False, server_default="0"
    )
    telegram_charge_id: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="star_payments")


class ProblemReport(Base):
    """Обращения «Сообщить о проблеме» для статистики."""

    __tablename__ = "problem_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    category: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text(), default="")
    scheduled_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )  # noqa: E501
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending")

    user: Mapped[User | None] = relationship(back_populates="notifications")
