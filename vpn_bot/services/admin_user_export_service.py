"""Текстовый отчёт: пользователи, трафик за всё время, WG-handshake по ключам (только чтение)."""  # noqa: E501

from __future__ import annotations

import os
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.config import get_settings
from vpn_bot.db.analytics_models import XrayTrafficLog
from vpn_bot.db.models import VpnKey
from vpn_bot.services.traffic_stats_service import all_users_total_traffic_gb
from vpn_bot.utils.moscow_schedule import MSK
from vpn_bot.wg_runtime import wg_show_dump
from vpn_bot.wg_utils import parse_wg_dump


async def _clean_xray_totals_by_user(session_analytics: AsyncSession) -> tuple[dict[int, float], dict[int, datetime | None]]:  # noqa: E501
    # Сумма дельт clean xray за всё время + последний online timestamp по user_id  # noqa: E501
    r = await session_analytics.execute(
        select(
            XrayTrafficLog.user_id,
            func.coalesce(
                func.sum(
                    func.coalesce(XrayTrafficLog.uplink_delta, 0)
                    + func.coalesce(XrayTrafficLog.downlink_delta, 0)
                ),
                0,
            ).label("bt"),
            func.max(XrayTrafficLog.logged_at).label("last_seen"),
        ).group_by(XrayTrafficLog.user_id)
    )
    gb_by_uid: dict[int, float] = {}
    online_by_uid: dict[int, datetime | None] = {}
    for uid, bt, last_online in r.all():
        gb_by_uid[int(uid)] = float(int(bt or 0)) / (1024**3)
        online_by_uid[int(uid)] = last_online
    return gb_by_uid, online_by_uid

def _fmt_handshake_ts(ts: int) -> str:  # noqa: E302
    if not ts:
        return "нет (ещё не было успешного handshake)"
    dt = datetime.fromtimestamp(ts, tz=UTC).astimezone(MSK)
    return dt.strftime("%Y-%m-%d %H:%M:%S МСК")


async def build_admin_users_traffic_handshake_report(
    session: AsyncSession,
    session_analytics: AsyncSession,
) -> str:
    settings = get_settings()
    iface = os.environ.get("TRAFFIC_WG_IFACE", settings.daemon_wg_interface)
    raw = await wg_show_dump(iface)
    peers = parse_wg_dump(raw)
    hs_by_pub: dict[str, int] = {
        str(p["public_key"]): int(p.get("handshake") or 0) for p in peers
    }

    rows = await all_users_total_traffic_gb(session, session_analytics)
    xray_gb_by_uid, xray_last_online_by_uid = await _clean_xray_totals_by_user(session_analytics)  # noqa: E501
    rows.sort(
        key=lambda t: (
            t[0].tg_username is None,
            (t[0].tg_username or "").lower(),
            t[0].id,
        )
    )

    keys_result = await session.execute(select(VpnKey).order_by(VpnKey.user_id, VpnKey.id))  # noqa: E501
    keys_by_uid: dict[int, list[VpnKey]] = {}
    for k in keys_result.scalars().all():
        keys_by_uid.setdefault(int(k.user_id), []).append(k)

    lines: list[str] = [
        "Отчёт: только чтение БД и «wg show … dump»; ключи и конфиги на сервере не менялись.",  # noqa: E501
        "Поле (2) — сумма дельт rx+tx из traffic_log за всё время (ГБ).",
        "Поле (3) — последний handshake по данным WG на интерфейсе демона сейчас; "  # noqa: E501
        "если пира нет в дампе, клиент сейчас не в таблице wg.",
        "Поле (4) — clean xray: трафик за всё время + последний online (аналог handshake).",  # noqa: E501
        "",
    ]

    for u, gb in rows:
        un = u.tg_username if u.tg_username else "—"
        lines.append(f"(1) tg username: @{un}  [tg_id={u.tg_id}]")
        lines.append(f"(2) трафик за всё время: {gb:.4f} ГБ")
        lines.append("(3) ключи, последнее рукопожатие:")
        ks = keys_by_uid.get(int(u.id), [])
        if not ks:
            lines.append("    — нет записей vpn_keys")
        else:
            for kk in ks:
                label = f"{kk.protocol}, файл {kk.config_filename}, active={kk.is_active}"  # noqa: E501
                pub = (kk.wg_peer_public_key or "").strip()
                if not pub:
                    lines.append(f"    — {label}: не WG / нет wg_peer_public_key в БД")  # noqa: E501
                    continue
                if pub not in hs_by_pub:
                    lines.append(
                        f"    — {label}: пир не в дампе wg (сейчас нет в списке интерфейса)"  # noqa: E501
                    )
                else:
                    lines.append(
                        f"    — {label}: {_fmt_handshake_ts(hs_by_pub[pub])}"
                    )
        xgb = float(xray_gb_by_uid.get(int(u.id), 0.0))
        last_online = xray_last_online_by_uid.get(int(u.id))
        if last_online is None:
            xonline = "нет"
        else:
            xonline = last_online.astimezone(MSK).strftime("%Y-%m-%d %H:%M:%S МСК")  # noqa: E501
        lines.append(f"(4) clean xray: трафик={xgb:.4f} ГБ; последний online={xonline}")  # noqa: E501
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
