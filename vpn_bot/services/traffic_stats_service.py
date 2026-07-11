from __future__ import annotations

import io
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.db.analytics_models import (
    TrafficLog,
    WhitelistBypassFeedback,
    XrayTrafficLog,
)
from vpn_bot.db.models import ProblemReport, User, VpnKey


class TrafficStatsService:
    def __init__(self, session_analytics: AsyncSession) -> None:
        self._a = session_analytics

    async def user_weekly_report(self, user_id: int) -> tuple[list[str], bytes | None]:
        since = datetime.now(UTC) - timedelta(days=7)
        day_col = func.date(TrafficLog.logged_at)
        r = await self._a.execute(
            select(
                day_col.label("d"),
                func.sum(
                    func.coalesce(TrafficLog.rx_delta, 0)
                    + func.coalesce(TrafficLog.tx_delta, 0)
                ).label("b"),
            )
            .where(
                TrafficLog.user_id == user_id,
                TrafficLog.logged_at >= since,
            )
            .group_by(day_col)
            .order_by(day_col)
        )
        rows: list[tuple[str, int]] = []
        for a, b in r.all():
            if isinstance(a, date):
                ds = a.isoformat()
            else:
                ds = str(a)
            rows.append((ds, int(b or 0)))
        total_b = sum(b for _, b in rows)
        total_gb = total_b / (1024**3)
        lines = [
            "Ваша статистика VPN (последние 7 дней).",
            "Учитываются только данные демона traffic_logger (снимки wg).",
            "",
        ]
        if not rows or total_b == 0:
            lines.append("Пока нет накопленных данных — демон должен работать на сервере с awg.")
        else:
            lines.append(f"Всего за период: ~{total_gb:.2f} ГБ (сумма приращений rx+tx).")
            lines.append("")
            for d, b in rows:
                gb = b / (1024**3)
                lines.append(f"• {d}: ~{gb:.2f} ГБ")
        chart = _chart_bytes_7d(rows) if len(rows) >= 2 else None
        return lines, chart


def _chart_bytes_7d(rows: list[tuple[str, int]]) -> bytes | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    try:
        xs = [datetime.strptime(d, "%Y-%m-%d").date() for d, _ in rows]
        ys = [b / (1024**3) for _, b in rows]
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.bar(xs, ys, color="#2d6cdf", width=0.7)
        ax.set_ylabel("ГБ / день")
        ax.set_title("Трафик по дням")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        fig.autofmt_xdate()
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=120)
        plt.close(fig)
        return buf.getvalue()
    except Exception:
        return None


async def count_keys_issued_between(
    session: AsyncSession, start: datetime, end: datetime
) -> int:
    r = await session.execute(
        select(func.count())
        .select_from(VpnKey)
        .where(VpnKey.generated_at >= start, VpnKey.generated_at < end)
    )
    return int(r.scalar_one() or 0)


async def top_users_traffic_between(
    session: AsyncSession,
    session_analytics: AsyncSession,
    start: datetime,
    end: datetime,
    limit: int = 5,
) -> list[tuple[int, int, float]]:
    """(internal_user_id, tg_id, gb)."""
    uid = TrafficLog.user_id
    r = await session_analytics.execute(
        select(
            uid,
            func.sum(
                func.coalesce(TrafficLog.rx_delta, 0)
                + func.coalesce(TrafficLog.tx_delta, 0)
            ),
        )
        .where(TrafficLog.logged_at >= start, TrafficLog.logged_at < end)
        .group_by(uid)
        .order_by(
            func.sum(
                func.coalesce(TrafficLog.rx_delta, 0)
                + func.coalesce(TrafficLog.tx_delta, 0)
            ).desc()
        )
        .limit(limit)
    )
    rows = r.all()
    if not rows:
        return []
    uids = [int(u) for u, _ in rows]
    r2 = await session.execute(select(User.id, User.tg_id).where(User.id.in_(uids)))
    tg_by_id = {int(i): int(tg) for i, tg in r2.all()}
    out: list[tuple[int, int, float]] = []
    for iu, b in rows:
        iu = int(iu)
        tg = tg_by_id.get(iu, 0)
        out.append((iu, tg, float(b or 0) / (1024**3)))
    return out


async def total_traffic_gb_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> float:
    r = await session_analytics.execute(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(TrafficLog.rx_delta, 0)
                    + func.coalesce(TrafficLog.tx_delta, 0)
                ),
                0,
            )
        ).where(TrafficLog.logged_at >= start, TrafficLog.logged_at < end)
    )
    b = int(r.scalar_one() or 0)
    return b / (1024**3)


async def count_distinct_traffic_users_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> int:
    r = await session_analytics.execute(
        select(func.count(func.distinct(TrafficLog.user_id))).where(
            TrafficLog.logged_at >= start,
            TrafficLog.logged_at < end,
        )
    )
    return int(r.scalar_one() or 0)


async def count_new_users_between(
    session: AsyncSession, start: datetime, end: datetime
) -> int:
    r = await session.execute(
        select(func.count())
        .select_from(User)
        .where(User.created_at >= start, User.created_at < end)
    )
    return int(r.scalar_one() or 0)


async def per_user_traffic_bytes_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> list[tuple[int, int]]:
    """Пользователи с положительной суммой дельт: (user_id, bytes)."""
    uid = TrafficLog.user_id
    r = await session_analytics.execute(
        select(
            uid,
            func.sum(
                func.coalesce(TrafficLog.rx_delta, 0)
                + func.coalesce(TrafficLog.tx_delta, 0)
            ),
        )
        .where(TrafficLog.logged_at >= start, TrafficLog.logged_at < end)
        .group_by(uid)
    )
    out: list[tuple[int, int]] = []
    for u, b in r.all():
        nb = int(b or 0)
        if nb > 0:
            out.append((int(u), nb))
    return out


async def keys_issued_by_protocol_between(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[str, int]:
    r = await session.execute(
        select(VpnKey.protocol, func.count())
        .where(VpnKey.generated_at >= start, VpnKey.generated_at < end)
        .group_by(VpnKey.protocol)
    )
    return {str(proto): int(n) for proto, n in r.all()}


async def count_problem_reports_between(
    session: AsyncSession, start: datetime, end: datetime
) -> int:
    r = await session.execute(
        select(func.count())
        .select_from(ProblemReport)
        .where(
            ProblemReport.created_at >= start,
            ProblemReport.created_at < end,
        )
    )
    return int(r.scalar_one() or 0)


async def count_whitelist_bypass_feedback_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> tuple[int, int]:
    """Число нажатий «работает» и «не работает» за интервал [start, end)."""
    r_ok = await session_analytics.execute(
        select(func.count())
        .select_from(WhitelistBypassFeedback)
        .where(
            WhitelistBypassFeedback.created_at >= start,
            WhitelistBypassFeedback.created_at < end,
            WhitelistBypassFeedback.works.is_(True),
        )
    )
    r_bad = await session_analytics.execute(
        select(func.count())
        .select_from(WhitelistBypassFeedback)
        .where(
            WhitelistBypassFeedback.created_at >= start,
            WhitelistBypassFeedback.created_at < end,
            WhitelistBypassFeedback.works.is_(False),
        )
    )
    return int(r_ok.scalar_one() or 0), int(r_bad.scalar_one() or 0)


async def all_users_total_traffic_gb(
    session: AsyncSession,
    session_analytics: AsyncSession,
) -> list[tuple[User, float]]:
    """Все пользователи и суммарный трафик (дельты rx+tx) за всё время, ГБ."""
    rsum = await session_analytics.execute(
        select(
            TrafficLog.user_id.label("uid"),
            func.coalesce(
                func.sum(
                    func.coalesce(TrafficLog.rx_delta, 0)
                    + func.coalesce(TrafficLog.tx_delta, 0)
                ),
                0,
            ).label("bt"),
        ).group_by(TrafficLog.user_id)
    )
    gb_by_uid: dict[int, int] = {int(u): int(b or 0) for u, b in rsum.all()}
    r_users = await session.execute(select(User).order_by(User.id))
    out: list[tuple[User, float]] = []
    for u in r_users.scalars().all():
        b = gb_by_uid.get(int(u.id), 0)
        out.append((u, float(b) / (1024**3)))
    return out


async def get_heavy_users_this_month(
    session: AsyncSession,
    session_analytics: AsyncSession,
    threshold_gb: float = 100.0,
) -> list[tuple[User, float]]:
    now = datetime.now(UTC)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    subq = (
        select(
            TrafficLog.user_id.label("uid"),
            func.coalesce(
                func.sum(
                    func.coalesce(TrafficLog.rx_delta, 0)
                    + func.coalesce(TrafficLog.tx_delta, 0)
                ),
                0,
            ).label("bt"),
        )
        .where(TrafficLog.logged_at >= start_of_month)
        .group_by(TrafficLog.user_id)
        .subquery()
    )
    r = await session_analytics.execute(
        select(subq.c.uid, subq.c.bt).where(subq.c.bt >= threshold_gb * (1024**3))
    )
    heavy_rows = r.all()
    if not heavy_rows:
        return []
    uids = [int(u) for u, _ in heavy_rows]
    r_users = await session.execute(select(User).where(User.id.in_(uids)))
    users_by_id = {u.id: u for u in r_users.scalars().all()}
    out: list[tuple[User, float]] = []
    for uid, bt in heavy_rows:
        u = users_by_id.get(int(uid))
        if u is not None:
            out.append((u, float(int(bt or 0)) / (1024**3)))
    out.sort(key=lambda x: -x[1])
    return out


async def count_distinct_clean_xray_users_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> int:
    r = await session_analytics.execute(
        select(func.count(func.distinct(XrayTrafficLog.user_id))).where(
            XrayTrafficLog.logged_at >= start,
            XrayTrafficLog.logged_at < end,
            (func.coalesce(XrayTrafficLog.uplink_delta, 0) + func.coalesce(XrayTrafficLog.downlink_delta, 0) > 0)
            | (XrayTrafficLog.online_count > 0),
        )
    )
    return int(r.scalar_one() or 0)


async def clean_xray_traffic_gb_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> float:
    r = await session_analytics.execute(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(XrayTrafficLog.uplink_delta, 0)
                    + func.coalesce(XrayTrafficLog.downlink_delta, 0)
                ),
                0,
            )
        ).where(XrayTrafficLog.logged_at >= start, XrayTrafficLog.logged_at < end)
    )
    b = int(r.scalar_one() or 0)
    return b / (1024**3)


async def count_all_active_vpn_users_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> int:
    wg_rows = await session_analytics.execute(
        select(func.distinct(TrafficLog.user_id)).where(
            TrafficLog.logged_at >= start,
            TrafficLog.logged_at < end,
            (func.coalesce(TrafficLog.rx_delta, 0) + func.coalesce(TrafficLog.tx_delta, 0) > 0),
        )
    )
    xray_rows = await session_analytics.execute(
        select(func.distinct(XrayTrafficLog.user_id)).where(
            XrayTrafficLog.logged_at >= start,
            XrayTrafficLog.logged_at < end,
            (func.coalesce(XrayTrafficLog.uplink_delta, 0) + func.coalesce(XrayTrafficLog.downlink_delta, 0) > 0)
            | (XrayTrafficLog.online_count > 0),
        )
    )
    users = {int(x[0]) for x in wg_rows.all()}
    users.update(int(x[0]) for x in xray_rows.all())
    return len(users)


async def latest_clean_xray_online_at_between(
    session_analytics: AsyncSession, start: datetime, end: datetime
) -> datetime | None:
    r = await session_analytics.execute(
        select(func.max(XrayTrafficLog.logged_at)).where(
            XrayTrafficLog.logged_at >= start,
            XrayTrafficLog.logged_at < end,
            XrayTrafficLog.online_count > 0,
        )
    )
    return r.scalar_one_or_none()
