"""Расширенный ежедневный дайджест для админов + графики CPU, RAM, сеть за сутки."""

from __future__ import annotations

import asyncio
import io
import json
import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import median

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto
from sqlalchemy import func, select

from vpn_bot.config import get_settings
from vpn_bot.constants import WG_HANDSHAKE_LAST_24H_SEC
from vpn_bot.db.analytics_models import DailyStats, HostMetricSample, TrafficLog
from vpn_bot.db.models import VpnKey
from vpn_bot.db.session import async_session_maker
from vpn_bot.db.session_analytics import async_session_maker_analytics
from vpn_bot.enums import VpnProtocol
from vpn_bot.services.traffic_stats_service import (
    clean_xray_traffic_gb_between,
    count_all_active_vpn_users_between,
    count_distinct_clean_xray_users_between,
    count_distinct_traffic_users_between,
    count_keys_issued_between,
    count_new_users_between,
    count_problem_reports_between,
    count_whitelist_bypass_feedback_between,
    get_heavy_users_this_month,
    keys_issued_by_protocol_between,
    latest_clean_xray_online_at_between,
    per_user_traffic_bytes_between,
    top_users_traffic_between,
    total_traffic_gb_between,
)
from vpn_bot.utils.journal_errors import count_journal_errors_by_unit
from vpn_bot.utils.moscow_schedule import MSK, moscow_day_bounds_utc
from vpn_bot.utils.text import split_telegram_message
from vpn_bot.wg_runtime import wg_show_dump
from vpn_bot.wg_utils import parse_wg_dump

logger = logging.getLogger(__name__)

_WG_PROTOCOLS = frozenset(
    {VpnProtocol.AMNEZIA_WG.value, VpnProtocol.WIREGUARD.value}
)
_CLEAN_XRAY_PROTOCOLS = frozenset(
    {
        VpnProtocol.XRAY_VLESS.value,
        VpnProtocol.XRAY_TROJAN.value,
        VpnProtocol.XRAY_VMESS.value,
        VpnProtocol.XRAY_SHADOWSOCKS.value,
    }
)


async def count_wg_keys_with_handshake_last_24h(session, wg_if: str) -> int:
    """
    Активные ключи в БД, для которых на wg dump есть handshake не старше 24 ч.
    Совпадает с тем, как пользователи «вернулись» на VPN недавно.
    """
    raw = await wg_show_dump(wg_if)
    peers = parse_wg_dump(raw)
    now_ts = int(datetime.now(UTC).timestamp())
    recent_pubs: set[str] = set()
    for p in peers:
        hs = int(p.get("handshake") or 0)
        if hs and (now_ts - hs) <= WG_HANDSHAKE_LAST_24H_SEC:
            recent_pubs.add(str(p["public_key"]))
    if not recent_pubs:
        return 0
    r = await session.execute(
        select(func.count()).select_from(VpnKey).where(
            VpnKey.is_active.is_(True),
            VpnKey.wg_peer_public_key.isnot(None),
            VpnKey.wg_peer_public_key != "",
            VpnKey.wg_peer_public_key.in_(recent_pubs),
        )
    )
    return int(r.scalar() or 0)


def _median_float(vals: list[float]) -> float:
    if not vals:
        return 0.0
    return float(median(vals))


async def try_insert_daily_stats_row(report_day: date, start: datetime, end: datetime) -> None:
    """Одна строка daily_stats за календарный день МСК (идемпотентно)."""
    async with async_session_maker() as session:
        async with async_session_maker_analytics() as session_a:
            existing = await session_a.scalar(
                select(DailyStats).where(DailyStats.stat_date == report_day)
            )
            if existing:
                return
            total_gb = await total_traffic_gb_between(session_a, start, end)
            users_n = await count_distinct_traffic_users_between(session_a, start, end)
            keys_c = await count_keys_issued_between(session, start, end)
            top = await top_users_traffic_between(session, session_a, start, end, 5)
            tb = total_gb * (1024**3)
            avg_mbps = (tb * 8) / 86400 / 1_000_000 if total_gb > 0 else 0.0
            top_uid = top[0][0] if top else None
            top_gb = top[0][2] if top else 0.0

            session_a.add(
                DailyStats(
                    stat_date=report_day,
                    total_users_tracked=users_n,
                    total_traffic_gb=total_gb,
                    avg_speed_mbps=avg_mbps,
                    top_user_id=top_uid,
                    top_traffic_gb=top_gb,
                    keys_issued_count=keys_c,
                    top_users_json=json.dumps(
                        [{"tg_id": tg, "gb": round(gb, 3)} for _, tg, gb in top],
                        ensure_ascii=False,
                    ),
                )
            )
            await session_a.commit()


async def _active_key_categories(
    session,
) -> tuple[int, int, int, int, int, float]:
    """
    only_wg, only_clean_xray, only_other, mixed, users_with_active_keys, mean_keys_per_user.
    """
    r = await session.execute(
        select(VpnKey.user_id, VpnKey.protocol).where(VpnKey.is_active.is_(True))
    )
    by_user: dict[int, set[str]] = defaultdict(set)
    for uid, proto in r.all():
        by_user[int(uid)].add(str(proto))
    only_wg = only_cx = only_other = mixed = 0
    for protos in by_user.values():
        has_wg = bool(protos & _WG_PROTOCOLS)
        has_cx = bool(protos & _CLEAN_XRAY_PROTOCOLS)
        has_other = bool(protos - _WG_PROTOCOLS - _CLEAN_XRAY_PROTOCOLS)
        kinds = int(has_wg) + int(has_cx) + int(has_other)
        if kinds >= 2:
            mixed += 1
        elif has_wg:
            only_wg += 1
        elif has_cx:
            only_cx += 1
        else:
            only_other += 1
    n_users = len(by_user)
    if n_users == 0:
        return 0, 0, 0, 0, 0, 0.0
    total_keys = await session.scalar(
        select(func.count()).select_from(VpnKey).where(VpnKey.is_active.is_(True))
    )
    mean_k = float(total_keys or 0) / float(n_users)
    return only_wg, only_cx, only_other, mixed, n_users, mean_k


async def _traffic_peak_hours_msk(
    session_analytics, start: datetime, end: datetime
) -> list[tuple[int, float]]:
    r = await session_analytics.execute(
        select(
            TrafficLog.logged_at,
            (
                func.coalesce(TrafficLog.rx_delta, 0)
                + func.coalesce(TrafficLog.tx_delta, 0)
            ),
        ).where(TrafficLog.logged_at >= start, TrafficLog.logged_at < end)
    )
    by_h: dict[int, int] = defaultdict(int)
    for la, delta in r.all():
        if la is None:
            continue
        h = la.astimezone(MSK).hour
        by_h[h] += int(delta or 0)
    out = [(h, by_h[h] / (1024**3)) for h in sorted(by_h)]
    return out


def _smooth_series(vals: list[float], w: int) -> list[float]:
    out: list[float] = []
    for i in range(len(vals)):
        a = max(0, i - w + 1)
        out.append(sum(vals[a : i + 1]) / (i - a + 1))
    return out


def _pick_smooth_window(n: int, smooth_window: int = 15) -> int:
    return min(smooth_window, max(3, n // 8))


def _fig_to_png_bytes(fig) -> bytes:
    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return buf.getvalue()


def _build_cpu_chart_png(
    samples: list[tuple[datetime, float, float, float | None, float | None]],
    smooth_window: int = 15,
) -> bytes | None:
    if len(samples) < 3:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception:
        return None

    xs = [s[0].astimezone(MSK) for s in samples]
    cpu_raw = [s[1] for s in samples]
    w = _pick_smooth_window(len(samples), smooth_window)
    cpu_s = _smooth_series(cpu_raw, w)

    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(xs, cpu_raw, alpha=0.22, color="#999", linewidth=0.8, label="CPU")
    ax.plot(xs, cpu_s, color="#1a5276", linewidth=1.3, label=f"сглажено (~{w} точек)")
    ax.axhline(
        max(cpu_raw),
        color="#c0392b",
        linestyle="--",
        linewidth=0.9,
        alpha=0.85,
        label=f"max {max(cpu_raw):.0f}%",
    )
    ax.set_ylabel("CPU %")
    ax.set_title("CPU за период (traffic_logger)")
    ax.legend(loc="upper right", fontsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M", tz=MSK))
    fig.autofmt_xdate()
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _build_ram_chart_png(
    samples: list[tuple[datetime, float, float, float | None, float | None]],
    smooth_window: int = 15,
) -> bytes | None:
    if len(samples) < 3:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception:
        return None

    xs = [s[0].astimezone(MSK) for s in samples]
    ram_raw = [s[2] for s in samples]
    w = _pick_smooth_window(len(samples), smooth_window)
    ram_s = _smooth_series(ram_raw, w)

    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(xs, ram_raw, alpha=0.22, color="#999", linewidth=0.8, label="RAM")
    ax.plot(xs, ram_s, color="#117a65", linewidth=1.3, label=f"сглажено (~{w} точек)")
    ax.axhline(
        max(ram_raw),
        color="#c0392b",
        linestyle="--",
        linewidth=0.9,
        alpha=0.85,
        label=f"max {max(ram_raw):.0f}%",
    )
    ax.set_ylabel("RAM %")
    ax.set_title("RAM за период (traffic_logger)")
    ax.legend(loc="upper right", fontsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M", tz=MSK))
    fig.autofmt_xdate()
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _build_network_chart_png(
    samples: list[tuple[datetime, float, float, float | None, float | None]],
    smooth_window: int = 15,
) -> bytes | None:
    net_rows = [
        (s[0], float(s[3]), float(s[4]))
        for s in samples
        if s[3] is not None and s[4] is not None
    ]
    if len(net_rows) < 3:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception:
        return None

    xs = [t[0].astimezone(MSK) for t in net_rows]
    rx_raw = [t[1] for t in net_rows]
    tx_raw = [t[2] for t in net_rows]
    w = _pick_smooth_window(len(net_rows), smooth_window)
    rx_s = _smooth_series(rx_raw, w)
    tx_s = _smooth_series(tx_raw, w)

    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.plot(xs, rx_raw, alpha=0.18, color="#999", linewidth=0.8)
    ax.plot(xs, tx_raw, alpha=0.18, color="#bbb", linewidth=0.8)
    ax.plot(xs, rx_s, color="#2874a6", linewidth=1.3, label="RX сглажено")
    ax.plot(xs, tx_s, color="#b9770e", linewidth=1.3, label="TX сглажено")
    ax.set_ylabel("Мбит/с")
    ax.set_title("Сеть (DAEMON_NET_INTERFACE, между минутными тиками)")
    ax.legend(loc="upper right", fontsize=7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m %H:%M", tz=MSK))
    fig.autofmt_xdate()
    fig.tight_layout()
    return _fig_to_png_bytes(fig)




async def _handshake_users_30d_series(session_analytics) -> list[tuple[date, int]]:
    start_utc = datetime.now(UTC) - timedelta(days=30)
    r = await session_analytics.execute(
        select(TrafficLog.logged_at, TrafficLog.user_id, TrafficLog.latest_handshake)
        .where(TrafficLog.logged_at >= start_utc)
        .order_by(TrafficLog.logged_at)
    )
    by_day: dict[date, set[int]] = defaultdict(set)
    for logged_at, uid, hs in r.all():
        if logged_at is None or uid is None:
            continue
        if int(hs or 0) <= 0:
            continue
        d = logged_at.astimezone(MSK).date()
        by_day[d].add(int(uid))
    out: list[tuple[date, int]] = []
    today = datetime.now(MSK).date()
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        out.append((d, len(by_day.get(d, set()))))
    return out


def _build_handshake_30d_chart_png(series: list[tuple[date, int]]) -> bytes | None:
    if len(series) < 2:
        return None
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt
    except Exception:
        return None

    xs = [d for d, _ in series]
    ys = [v for _, v in series]
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.plot(xs, ys, color="#8e44ad", linewidth=1.5, marker="o", markersize=2.5)
    ax.set_ylabel("Пользователи")
    ax.set_title("Активные handshake-пользователи за 30 дней")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    fig.autofmt_xdate()
    fig.tight_layout()
    return _fig_to_png_bytes(fig)

def _build_host_charts_png_bundle(
    samples: list[tuple[datetime, float, float, float | None, float | None]],
) -> tuple[bytes | None, bytes | None, bytes | None]:
    return (
        _build_cpu_chart_png(samples),
        _build_ram_chart_png(samples),
        _build_network_chart_png(samples),
    )


async def build_admin_digest_text_and_chart(
    report_day: date,
    start: datetime,
    end: datetime,
    *,
    purged_wg_keys: int | None = None,
) -> tuple[str, list[tuple[str, bytes]]]:
    settings = get_settings()
    async with async_session_maker() as session:
        async with async_session_maker_analytics() as session_a:
            new_users = await count_new_users_between(session, start, end)
            active_users = await count_distinct_traffic_users_between(
                session_a, start, end
            )
            clean_xray_active_users = await count_distinct_clean_xray_users_between(
                session_a, start, end
            )
            all_active_vpn_users = await count_all_active_vpn_users_between(
                session_a, start, end
            )
            total_gb = await total_traffic_gb_between(session_a, start, end)
            clean_xray_gb = await clean_xray_traffic_gb_between(session_a, start, end)
            clean_xray_last_online_at = await latest_clean_xray_online_at_between(
                session_a, start, end
            )
            per_user = await per_user_traffic_bytes_between(session_a, start, end)
            gbs = [b / (1024**3) for _, b in per_user]
            med_gb = _median_float(gbs)
            top = await top_users_traffic_between(session, session_a, start, end, 5)
            top5_gb = sum(gb for _, _, gb in top)
            tail_gb = max(0.0, total_gb - top5_gb)
            tail_pct = (100.0 * tail_gb / total_gb) if total_gb > 0 else 0.0
            top_pct = (100.0 * top5_gb / total_gb) if total_gb > 0 else 0.0

            heavy_users = await get_heavy_users_this_month(session, session_a, 100.0)
            heavy_count = len(heavy_users)

            keys_by_proto = await keys_issued_by_protocol_between(session, start, end)
            keys_total_issued = sum(keys_by_proto.values())
            clean_xray_keys_issued = sum(
                int(keys_by_proto.get(proto, 0))
                for proto in (
                    VpnProtocol.XRAY_VLESS.value,
                    VpnProtocol.XRAY_TROJAN.value,
                    VpnProtocol.XRAY_VMESS.value,
                    VpnProtocol.XRAY_SHADOWSOCKS.value,
                )
            )
            ow, ocx, ooth, mx, n_key_users, mean_keys = await _active_key_categories(session)

            wg_iface = (settings.daemon_wg_interface or "").strip() or "awg0"
            wg_keys_hs_24h = await count_wg_keys_with_handshake_last_24h(
                session, wg_iface
            )

            peak = await _traffic_peak_hours_msk(session_a, start, end)
            prob_n = await count_problem_reports_between(session, start, end)
            wl_ok, wl_bad = await count_whitelist_bypass_feedback_between(
                session_a, start, end
            )

            samp = (
                await session_a.execute(
                    select(
                        HostMetricSample.logged_at,
                        HostMetricSample.cpu_percent,
                        HostMetricSample.ram_percent,
                        HostMetricSample.net_rx_mbps,
                        HostMetricSample.net_tx_mbps,
                    )
                    .where(
                        HostMetricSample.logged_at >= start,
                        HostMetricSample.logged_at < end,
                    )
                    .order_by(HostMetricSample.logged_at)
                )
            ).all()
            samples_report_day = [
                (
                    row[0],
                    float(row[1]),
                    float(row[2]),
                    float(row[3]) if row[3] is not None else None,
                    float(row[4]) if row[4] is not None else None,
                )
                for row in samp
            ]
            chart_samples = list(samples_report_day)
            chart_fallback_used = False
            if len(chart_samples) < 3:
                now_utc = datetime.now(UTC)
                fb_start = now_utc - timedelta(hours=48)
                samp_fb = (
                    await session_a.execute(
                        select(
                            HostMetricSample.logged_at,
                            HostMetricSample.cpu_percent,
                            HostMetricSample.ram_percent,
                            HostMetricSample.net_rx_mbps,
                            HostMetricSample.net_tx_mbps,
                        )
                        .where(
                            HostMetricSample.logged_at >= fb_start,
                            HostMetricSample.logged_at <= now_utc,
                        )
                        .order_by(HostMetricSample.logged_at)
                    )
                ).all()
                chart_samples = [
                    (
                        row[0],
                        float(row[1]),
                        float(row[2]),
                        float(row[3]) if row[3] is not None else None,
                        float(row[4]) if row[4] is not None else None,
                    )
                    for row in samp_fb
                ]
                chart_fallback_used = len(chart_samples) >= 3

    async with async_session_maker_analytics() as _sa2:
        hs30_series = await _handshake_users_30d_series(_sa2)

    journal_total, journal_lines = await asyncio.to_thread(
        count_journal_errors_by_unit,
        start,
        end,
        settings.admin_journal_unit_list,
    )

    lines: list[str] = [
        f"📊 Дайджест за {report_day.isoformat()} (сутки по МСК, границы в UTC для БД).",
    ]
    if purged_wg_keys is not None and settings.stale_wg_key_days >= 1:
        lines.append(
            f"Удалено неактивных WG-ключей (>{settings.stale_wg_key_days} дн.): {purged_wg_keys}"
        )
    lines.extend(
        [
            "",
            "Пользователи:",
            f"  • новых за сутки: {new_users}",
            f"  • активных по трафику WG (есть логи wg): {active_users}",
            f"  • активных пользователей clean xray (трафик/online): {clean_xray_active_users}",
            f"  • активно использовали VPN (WG ∪ clean xray): {all_active_vpn_users}",
            f"  • последний online clean xray (аналог handshake): "
            + (clean_xray_last_online_at.astimezone(MSK).strftime("%Y-%m-%d %H:%M:%S MSK") if clean_xray_last_online_at else "нет за сутки"),
            "",
            "Ключи:",
            f"  • WG-ключей с handshake за последние 24 ч (снимок wg): {wg_keys_hs_24h}",
            f"  • выдано за сутки (всего): {keys_total_issued}",
            f"  • новых ключей clean xray за сутки: {clean_xray_keys_issued}",
        ]
    )
    for proto, n in sorted(keys_by_proto.items(), key=lambda x: -x[1]):
        lines.append(f"    — {proto}: {n}")
    pct_base = ow + ocx + ooth + mx
    lines.extend(
        [
            f"  • пользователей с ≥1 активным ключом: {n_key_users}",
            f"  • среднее активных ключей на такого пользователя: {mean_keys:.2f}",
            "  • разбивка по типам активных ключей пользователя:",
            f"    — только WG (Amnezia WG / WireGuard): {ow}"
            + (f" ({100 * ow / pct_base:.0f}%)" if pct_base else ""),
            f"    — только clean xray: {ocx}"
            + (f" ({100 * ocx / pct_base:.0f}%)" if pct_base else ""),
            f"    — только прочие (не WG и не clean xray): {ooth}"
            + (f" ({100 * ooth / pct_base:.0f}%)" if pct_base else ""),
            f"    — смешанно: {mx}" + (f" ({100 * mx / pct_base:.0f}%)" if pct_base else ""),
            "",
        ]
    )
    lines.extend(
        [
            "",
            "Бот и обращения:",
            f"  • записей journalctl -p err: {journal_total}",
        ]
    )
    for jl in journal_lines:
        lines.append(f"      — {jl}")
    lines.append(f"  • обращений «Сообщить о проблеме» (БД): {prob_n}")
    wl_total = wl_ok + wl_bad
    if wl_total > 0:
        lines.append(
            f"  • белые списки (beta) — нажатия: «работает» {wl_ok} "
            f"({100.0 * wl_ok / wl_total:.0f}%), «не работает» {wl_bad} "
            f"({100.0 * wl_bad / wl_total:.0f}%); всего {wl_total}"
        )
    else:
        lines.append("  • белые списки (beta) — отзывы за сутки: нет нажатий")
    net_pts = sum(
        1 for s in samples_report_day if s[3] is not None and s[4] is not None
    )
    lines.extend(
        [
            "",
            f"Точек метрик хоста за сутки отчёта: {len(samples_report_day)} "
            f"(с полем сети: {net_pts}; первый тик после рестарта демона без Мбит/с).",
        ]
    )
    if chart_fallback_used:
        lines.append(
            "Графики построены по последним 48 ч (за сутки отчёта точек < 3 — "
            "так бывает сразу после первого запуска демона или если сутки были пустые)."
        )
    lines.append("Ниже альбом из до 4 графиков: CPU, RAM, сеть (Мбит/с), handshake-пользователи за 30 дней.")

    cpu_png, ram_png, net_png = await asyncio.to_thread(
        _build_host_charts_png_bundle, chart_samples
    )
    hs30_png = await asyncio.to_thread(_build_handshake_30d_chart_png, hs30_series)
    charts: list[tuple[str, bytes]] = []
    if cpu_png:
        charts.append(("host_cpu.png", cpu_png))
    if ram_png:
        charts.append(("host_ram.png", ram_png))
    if net_png:
        charts.append(("host_network.png", net_png))
    if hs30_png:
        charts.append(("handshake_30d.png", hs30_png))
    return "\n".join(lines), charts


async def send_admin_digest(
    bot: Bot,
    report_day: date,
    *,
    purged_wg_keys: int | None = None,
) -> None:
    settings = get_settings()
    if not settings.admin_ids:
        return
    start, end = moscow_day_bounds_utc(report_day)
    try:
        text, charts_list = await build_admin_digest_text_and_chart(
            report_day, start, end, purged_wg_keys=purged_wg_keys
        )
    except Exception:
        logger.exception("build_admin_digest failed")
        return
    for aid in settings.admin_ids:
        for part in split_telegram_message(text, 3800):
            try:
                await bot.send_message(aid, part)
            except Exception as e:
                logger.warning("admin digest msg %s: %s", aid, e)
        if charts_list:
            cap = f"Дайджест {report_day.isoformat()}: метрики хоста"
            try:
                media = [
                    InputMediaPhoto(
                        media=BufferedInputFile(data, filename=fn),
                        caption=cap if i == 0 else None,
                    )
                    for i, (fn, data) in enumerate(charts_list)
                ]
                await bot.send_media_group(aid, media)
            except Exception as e:
                logger.warning("admin digest media_group %s: %s", aid, e)
                for fn, data in charts_list:
                    try:
                        await bot.send_photo(
                            aid, BufferedInputFile(data, filename=fn)
                        )
                    except Exception as e2:
                        logger.warning("admin digest chart %s %s: %s", aid, fn, e2)
