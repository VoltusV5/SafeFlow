"""Расписание по календарным суткам Europe/Moscow (МСК)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def moscow_now() -> datetime:
    return datetime.now(UTC).astimezone(MSK)


def moscow_day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    """Начало (вкл.) и конец (искл.) календарного дня d по МСК, в UTC."""
    start_local = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=MSK)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def yesterday_moscow_date(ref: datetime | None = None) -> date:
    """Вчерашняя дата по календарю МСК относительно ref (по умолчанию сейчас)."""  # noqa: E501
    m = (ref or datetime.now(UTC)).astimezone(MSK)
    return (m - timedelta(days=1)).date()


def in_moscow_daily_window(
    hour: int = 8,
    minute_max_exclusive: int = 5,
    ref: datetime | None = None,
) -> bool:
    """True, если сейчас по МСК hour:00 … hour:(minute_max_exclusive-1)."""
    m = (ref or datetime.now(UTC)).astimezone(MSK)
    return m.hour == hour and m.minute < minute_max_exclusive


def seconds_until_next_moscow_time(
    hour: int,
    minute: int = 0,
    ref: datetime | None = None,
) -> float:
    """Секунды до ближайшего наступления hour:minute по МСК (строго после ref)."""  # noqa: E501
    now = ref or datetime.now(UTC)
    m = now.astimezone(MSK)
    target = m.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if m >= target:
        target += timedelta(days=1)
    return max(
        0.0, (target.astimezone(UTC) - now.astimezone(UTC)).total_seconds()
    )  # noqa: E501
