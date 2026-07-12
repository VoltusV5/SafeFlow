"""Таблицы только в analytics DB (см. session_analytics). user_id — ссылка на users.id логически, без FK."""  # noqa: E501

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,  # noqa: F401, E501
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from vpn_bot.db.analytics_base import BaseAnalytics


class TrafficLog(BaseAnalytics):
    __tablename__ = "traffic_log"
    # Составной индекс для быстрого поиска последней записи пользователя.
    # Без него при 6M+ строках каждый SELECT ... WHERE user_id=X ORDER BY logged_at DESC LIMIT 1  # noqa: E501
    # делал temp B-tree sort по ~1.3M строкам на пользователя => 60% CPU в traffic_logger.  # noqa: E501
    __table_args__ = (
        Index("ix_traffic_log_user_id_logged_at", "user_id", "logged_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer(), index=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # noqa: E501
    rx_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)
    tx_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)
    rx_delta: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    tx_delta: Mapped[int | None] = mapped_column(BigInteger(), nullable=True)
    latest_handshake: Mapped[int] = mapped_column(Integer(), default=0)
    session_duration_sec: Mapped[int | None] = mapped_column(
        Integer(), nullable=True
    )  # noqa: E501


class DailyStats(BaseAnalytics):
    __tablename__ = "daily_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stat_date: Mapped[date] = mapped_column(Date(), unique=True, index=True)
    total_users_tracked: Mapped[int] = mapped_column(Integer(), default=0)
    total_traffic_gb: Mapped[float] = mapped_column(Float(), default=0.0)
    avg_speed_mbps: Mapped[float] = mapped_column(Float(), default=0.0)
    top_user_id: Mapped[int | None] = mapped_column(Integer(), nullable=True)
    top_traffic_gb: Mapped[float] = mapped_column(Float(), default=0.0)
    keys_issued_count: Mapped[int] = mapped_column(Integer(), default=0)
    top_users_json: Mapped[str | None] = mapped_column(Text(), nullable=True)


class HostMetricSample(BaseAnalytics):
    """Снимки CPU/RAM/сети (~1 раз в минуту)."""

    __tablename__ = "host_metric_samples"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # noqa: E501
    cpu_percent: Mapped[float] = mapped_column(Float())
    ram_percent: Mapped[float] = mapped_column(Float())
    net_rx_mbps: Mapped[float | None] = mapped_column(Float(), nullable=True)
    net_tx_mbps: Mapped[float | None] = mapped_column(Float(), nullable=True)


class WhitelistBypassFeedback(BaseAnalytics):
    """Нажатия «работает / не работает» у инструкции обхода белых списков (analytics DB)."""  # noqa: E501

    __tablename__ = "whitelist_bypass_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # noqa: E501
    works: Mapped[bool] = (
        mapped_column()
    )  # True — «работает при белых», False — «не работает»  # noqa: E501


class XrayTrafficLog(BaseAnalytics):
    __tablename__ = "xray_traffic_log"
    # Составной индекс для быстрого поиска последней записи пользователя по Xray.  # noqa: E501
    __table_args__ = (
        Index("ix_xray_traffic_log_user_id_logged_at", "user_id", "logged_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer(), index=True)
    protocol: Mapped[str] = mapped_column(Text())
    email: Mapped[str] = mapped_column(Text(), index=True)
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True
    )  # noqa: E501
    uplink_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)
    downlink_bytes: Mapped[int] = mapped_column(BigInteger(), default=0)
    uplink_delta: Mapped[int | None] = mapped_column(
        BigInteger(), nullable=True
    )  # noqa: E501
    downlink_delta: Mapped[int | None] = mapped_column(
        BigInteger(), nullable=True
    )  # noqa: E501
    online_count: Mapped[int] = mapped_column(Integer(), default=0)
