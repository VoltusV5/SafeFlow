from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

from aiogram import Bot
from sqlalchemy import delete, desc, select, update

from vpn_bot.config import get_settings
from vpn_bot.constants import WG_ACTIVE_HANDSHAKE_SEC
from vpn_bot.db.analytics_models import HostMetricSample, TrafficLog, XrayTrafficLog
from vpn_bot.db.models import VpnKey
from vpn_bot.db.session import async_session_maker, init_db
from vpn_bot.db.session_analytics import (
    async_session_maker_analytics,
    init_analytics_db,
)
from vpn_bot.enums import VpnProtocol
from vpn_bot.services.admin_digest_service import (
    send_admin_digest,
    try_insert_daily_stats_row,
)
from vpn_bot.services.key_cleanup_service import purge_stale_wg_keys
from vpn_bot.utils.moscow_schedule import (
    in_moscow_daily_window,
    moscow_day_bounds_utc,
    moscow_now,
    yesterday_moscow_date,
)
from vpn_bot.utils.sqlite_backup import resolve_sqlite_path
from vpn_bot.wg_runtime import wg_show_dump
from vpn_bot.wg_utils import parse_wg_dump

logger = logging.getLogger(__name__)

# (bytes_sent, bytes_recv, monotonic_ts) для расчёта Мбит/с между тиками
_prev_net_counters: tuple[int, int, float] | None = None

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STATE_FILE = _PROJECT_ROOT / ".moscow_morning_jobs_done"
_XRAY_PROTOCOLS = frozenset(
    {
        VpnProtocol.XRAY_VLESS.value,
        VpnProtocol.XRAY_TROJAN.value,
        VpnProtocol.XRAY_VMESS.value,
        VpnProtocol.XRAY_SHADOWSOCKS.value,
    }
)


def _load_moscow_jobs_done_date() -> date | None:
    try:
        return date.fromisoformat(
            _STATE_FILE.read_text(encoding="utf-8").strip()
        )  # noqa: E501
    except OSError:
        return None
    except ValueError:
        return None


def _save_moscow_jobs_done_date(d: date) -> None:
    try:
        _STATE_FILE.write_text(d.isoformat(), encoding="utf-8")
    except OSError as e:
        logger.warning("cannot persist moscow jobs date: %s", e)


async def _append_host_metric_sample(session) -> None:
    global _prev_net_counters
    try:
        import psutil

        s = get_settings()
        iface = (s.daemon_net_interface or "").strip()
        rx_mbps: float | None = None
        tx_mbps: float | None = None
        try:
            if iface:
                per = psutil.net_io_counters(pernic=True)
                nic = per.get(iface) if isinstance(per, dict) else None
            else:
                nic = None
            if nic is None:
                nic = psutil.net_io_counters(pernic=False)
            now_m = time.monotonic()
            if _prev_net_counters is not None:
                ps0, pr0, pm0 = _prev_net_counters
                dt = now_m - pm0
                if dt > 0.05:
                    ds = int(nic.bytes_sent) - ps0
                    dr = int(nic.bytes_recv) - pr0
                    if ds >= 0 and dr >= 0:
                        tx_mbps = (ds * 8.0) / dt / 1_000_000.0
                        rx_mbps = (dr * 8.0) / dt / 1_000_000.0
            _prev_net_counters = (
                int(nic.bytes_sent),
                int(nic.bytes_recv),
                now_m,
            )  # noqa: E501
        except Exception:
            logger.debug(
                "net_io_counters for host sample failed", exc_info=True
            )  # noqa: E501

        cpu = float(psutil.cpu_percent(interval=0.12))
        vm = psutil.virtual_memory()
        session.add(
            HostMetricSample(
                logged_at=datetime.now(UTC),
                cpu_percent=cpu,
                ram_percent=float(vm.percent),
                net_rx_mbps=rx_mbps,
                net_tx_mbps=tx_mbps,
            )
        )
    except Exception:
        logger.debug("host metric sample failed", exc_info=True)


async def _prune_host_metric_samples(session) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=14)
    await session.execute(
        delete(HostMetricSample).where(HostMetricSample.logged_at < cutoff)
    )


async def _log_traffic_tick(session, session_analytics, wg_if: str) -> None:
    raw = await wg_show_dump(wg_if)
    peers = parse_wg_dump(raw)
    r = await session.execute(
        select(VpnKey.wg_peer_public_key, VpnKey.user_id).where(
            VpnKey.is_active.is_(True),
            VpnKey.wg_peer_public_key.isnot(None),
        )
    )
    peer_user = {a: int(b) for a, b in r.all() if a}
    now = datetime.now(UTC)
    now_ts = int(now.timestamp())

    for p in peers:
        pub = str(p["public_key"])
        uid = peer_user.get(pub)
        if uid is None:
            continue
        rx = int(p["rx"])
        tx = int(p["tx"])
        hs = int(p.get("handshake") or 0)
        last = (
            await session_analytics.execute(
                select(TrafficLog)
                .where(TrafficLog.user_id == uid)
                .order_by(desc(TrafficLog.logged_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        if last:
            drx = max(0, rx - int(last.rx_bytes))
            dtx = max(0, tx - int(last.tx_bytes))
        else:
            drx = dtx = 0
        dur = None
        if hs:
            dur = max(0, int(now.timestamp()) - hs)
        session_analytics.add(
            TrafficLog(
                user_id=uid,
                logged_at=now,
                rx_bytes=rx,
                tx_bytes=tx,
                rx_delta=drx,
                tx_delta=dtx,
                latest_handshake=hs,
                session_duration_sec=dur,
            )
        )
        active = (drx + dtx > 0) or (hs and (now_ts - hs) <= WG_ACTIVE_HANDSHAKE_SEC)
        if active:
            await session.execute(
                update(VpnKey)
                .where(
                    VpnKey.wg_peer_public_key == pub,
                    VpnKey.is_active.is_(True),
                )
                .values(last_activity_at=now)
            )


def _run_cmd(cmd: list[str], timeout: int = 15) -> str:
    p = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, check=False
    )  # noqa: E501
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "").strip()[:500])
    return p.stdout or ""


def _extract_key_id_from_url(proto: str, key_value: str) -> str | None:
    try:
        if proto == VpnProtocol.XRAY_VLESS.value and key_value.startswith(
            "vless://"
        ):  # noqa: E501
            return key_value.split("vless://", 1)[1].split("@", 1)[0]
        if proto == VpnProtocol.XRAY_TROJAN.value and key_value.startswith(
            "trojan://"
        ):  # noqa: E501
            return unquote(key_value.split("trojan://", 1)[1].split("@", 1)[0])
    except Exception:
        return None
    return None


def _build_xray_email_user_map(
    active_keys: list[VpnKey], config_json: dict
) -> dict[str, tuple[int, str]]:  # noqa: E501
    by_proto_key: dict[tuple[str, str], int] = {}
    for k in active_keys:
        kid = _extract_key_id_from_url(str(k.protocol), str(k.key_value))
        if kid:
            by_proto_key[(str(k.protocol), kid)] = int(k.user_id)

    out: dict[str, tuple[int, str]] = {}
    for ib in config_json.get("inbounds", []):
        tag = str(ib.get("tag") or "")
        if tag == "in-vless":
            proto = VpnProtocol.XRAY_VLESS.value
            key_field = "id"
        elif tag == "in-trojan":
            proto = VpnProtocol.XRAY_TROJAN.value
            key_field = "password"
        elif tag == "in-vmess":
            proto = VpnProtocol.XRAY_VMESS.value
            key_field = "id"
        elif tag == "in-ss":
            proto = VpnProtocol.XRAY_SHADOWSOCKS.value
            key_field = "password"
        else:
            continue
        clients = (ib.get("settings") or {}).get("clients") or []
        for c in clients:
            email = str(c.get("email") or "")
            kval = str(c.get(key_field) or "")
            uid = by_proto_key.get((proto, kval))
            if email and uid is not None:
                out[email] = (uid, proto)
    return out


async def _log_clean_xray_tick(session, session_analytics) -> None:  # noqa: C901, E501
    s = get_settings()
    ctr = (s.clean_xray_container or "vpn-clean-xray").strip()

    active_keys_rows = await session.execute(
        select(VpnKey).where(
            VpnKey.is_active.is_(True), VpnKey.protocol.in_(_XRAY_PROTOCOLS)
        )  # noqa: E501
    )
    active_keys = list(active_keys_rows.scalars().all())
    if not active_keys:
        return

    with open(
        "/root/vpn-telegram-bot/deploy/clean-xray/config.json", "r", encoding="utf-8"
    ) as f:  # noqa: E501
        cfg = json.load(f)
    email_map = _build_xray_email_user_map(active_keys, cfg)
    if not email_map:
        return

    stats_raw = _run_cmd(
        [
            "docker",
            "exec",
            ctr,
            "xray",
            "api",
            "statsquery",
            f"--server=127.0.0.1:{int(s.clean_xray_api_port)}",  # noqa: E501
        ]
    )
    stats_doc = json.loads(stats_raw or "{}")

    online_raw = _run_cmd(
        [
            "docker",
            "exec",
            ctr,
            "xray",
            "api",
            "statsgetallonlineusers",
            f"--server=127.0.0.1:{int(s.clean_xray_api_port)}",  # noqa: E501
        ]
    )
    online_doc = json.loads(online_raw or "{}")
    online_names = set(str(x) for x in (online_doc.get("users") or []))

    totals: dict[str, dict[str, int]] = {}
    for st in stats_doc.get("stat") or []:
        name = str(st.get("name") or "")
        if not name.startswith("user>>>"):
            continue
        # user>>>EMAIL>>>traffic>>>uplink/downlink
        parts = name.split(">>>")
        if len(parts) < 4:
            continue
        email = parts[1]
        metric = parts[3]
        if email not in email_map:
            continue
        val = int(st.get("value") or 0)
        slot = totals.setdefault(email, {"uplink": 0, "downlink": 0})
        if metric in ("uplink", "downlink"):
            slot[metric] = val

    now = datetime.now(UTC)
    for email, vals in totals.items():
        mapped = email_map.get(email)
        if mapped is None:
            continue
        uid, proto = mapped
        last = (
            await session_analytics.execute(
                select(XrayTrafficLog)
                .where(
                    XrayTrafficLog.user_id == uid, XrayTrafficLog.email == email
                )  # noqa: E501
                .order_by(desc(XrayTrafficLog.logged_at))
                .limit(1)
            )
        ).scalar_one_or_none()
        up = int(vals.get("uplink") or 0)
        down = int(vals.get("downlink") or 0)
        if last:
            dup = max(0, up - int(last.uplink_bytes))
            ddown = max(0, down - int(last.downlink_bytes))
        else:
            dup = ddown = 0
        online_key = f"user>>>{email}>>>online"
        online_count = 1 if online_key in online_names else 0

        session_analytics.add(
            XrayTrafficLog(
                user_id=uid,
                protocol=proto,
                email=email,
                logged_at=now,
                uplink_bytes=up,
                downlink_bytes=down,
                uplink_delta=dup,
                downlink_delta=ddown,
                online_count=online_count,
            )
        )
        if (dup + ddown > 0) or online_count > 0:
            await session.execute(
                update(VpnKey)
                .where(
                    VpnKey.user_id == uid,
                    VpnKey.protocol == proto,
                    VpnKey.is_active.is_(True),
                )
                .values(last_activity_at=now)
            )


async def _morning_digest_and_stats(
    bot: Bot, report_day: date, purged_keys: int
) -> None:  # noqa: E501
    start, end = moscow_day_bounds_utc(report_day)
    try:
        await try_insert_daily_stats_row(report_day, start, end)
    except Exception:
        logger.exception("daily_stats insert")
    try:
        await send_admin_digest(bot, report_day, purged_wg_keys=purged_keys)
    except Exception:
        logger.exception("send_admin_digest")


async def _weekly_db_backup_reminder(bot: Bot) -> None:
    """Только текст: файл БД в Telegram не отправляем (лимит размера и лишняя нагрузка на SQLite)."""  # noqa: E501
    s = get_settings()
    if not s.admin_ids:
        return
    main_path = resolve_sqlite_path(s.database_url)
    analytics_path = resolve_sqlite_path(s.analytics_database_url)
    path_hint = ""
    if main_path is not None and main_path.is_file():
        path_hint = f"\n\nОсновная БД:\n{main_path}\n"
        if analytics_path is not None and analytics_path.is_file():
            path_hint += f"Аналитика (трафик, метрики):\n{analytics_path}\n"
        path_hint += (
            "\nСкопируйте на свой ПК (scp/sftp) или снимок: "
            'sqlite3 путь_к_бд ".backup backup.sqlite3"'
        )
    else:
        path_hint = (
            f"\n\nПроверьте DATABASE_URL / ANALYTICS_DATABASE_URL в .env.\n"
            f"Сейчас: {s.database_url[:120]}"
        )
    text = (
        "📅 Еженедельное напоминание о бэкапе базы данных.\n\n"
        "Сделайте копию SQLite у себя (облако, другой ПК, внешний диск). "
        "Файл БД в Telegram больше не отправляется — так надёжнее и без лимита размера."  # noqa: E501
        + path_hint
    )
    for aid in s.admin_ids:
        try:
            await bot.send_message(aid, text)
        except Exception as e:
            logger.warning("admin backup reminder %s: %s", aid, e)


async def _run_moscow_morning_jobs(
    bot: Bot, last_jobs_date: date | None
) -> date | None:  # noqa: C901, E501
    """Один раз за календарный день МСК в окне 08:00."""
    m = moscow_now()
    today_msk = m.date()
    persisted = _load_moscow_jobs_done_date()
    done_for = last_jobs_date or persisted
    if done_for == today_msk:
        return done_for
    if not in_moscow_daily_window():
        return done_for

    report_day = yesterday_moscow_date()
    s = get_settings()
    purged = 0
    try:
        async with async_session_maker() as session:
            purged = await purge_stale_wg_keys(session, s.stale_wg_key_days)
            await session.commit()
    except Exception:
        logger.exception("stale wg key purge")

    try:
        async with async_session_maker_analytics() as session_a:
            await _prune_host_metric_samples(session_a)
            await session_a.commit()
    except Exception:
        logger.exception("prune host_metric_samples")

    try:
        await _morning_digest_and_stats(bot, report_day, purged)
    except Exception:
        logger.exception("morning digest")

    if m.weekday() == int(get_settings().admin_backup_weekday) % 7:
        try:
            await _weekly_db_backup_reminder(bot)
        except Exception:
            logger.exception("weekly backup reminder")

    return today_msk


async def run_loop() -> None:  # noqa: C901
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await init_analytics_db()
    s = get_settings()
    wg_if = os.environ.get("TRAFFIC_WG_IFACE", s.daemon_wg_interface)
    bot = Bot(s.bot_token)
    last_reported_jobs: date | None = _load_moscow_jobs_done_date()
    try:
        while True:
            try:
                new_d = await _run_moscow_morning_jobs(bot, last_reported_jobs)
                if new_d is not None and new_d != last_reported_jobs:
                    _save_moscow_jobs_done_date(new_d)
                    last_reported_jobs = new_d
            except Exception:
                logger.exception("moscow morning jobs")
            try:
                async with async_session_maker() as session:
                    async with async_session_maker_analytics() as session_a:
                        try:
                            try:
                                await _log_traffic_tick(
                                    session, session_a, wg_if
                                )  # noqa: E501
                            except Exception:
                                logger.exception("wg traffic tick")
                            try:
                                await _log_clean_xray_tick(session, session_a)
                            except Exception:
                                logger.exception("clean xray traffic tick")
                            await _append_host_metric_sample(session_a)
                            await session.commit()
                            await session_a.commit()
                        except Exception:
                            await session.rollback()
                            await session_a.rollback()
                            raise
            except Exception:
                logger.exception("traffic tick")
            await asyncio.sleep(60)
    finally:
        await bot.session.close()


def main() -> None:
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
