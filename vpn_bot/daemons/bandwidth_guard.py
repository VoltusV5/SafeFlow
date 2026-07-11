from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.config import get_settings
from vpn_bot.constants import (
    BANDWIDTH_FAIR_SHARE_POOL_MBPS,
    BANDWIDTH_FAIR_SHARE_THRESHOLD_MBPS,
    BANDWIDTH_MAX_PER_USER_MBPS,
    CPU_FAIR_SHARE_PERCENT,
    WG_ACTIVE_HANDSHAKE_SEC,
)
from vpn_bot.db.models import UserLimit, VpnKey
from vpn_bot.db.session import async_session_maker, init_db
from vpn_bot.wg_runtime import wg_show_dump
from vpn_bot.wg_utils import parse_wg_dump, read_proc_net_dev

logger = logging.getLogger(__name__)


def _append_log(path: str, msg: str) -> None:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.now(UTC).isoformat()} {msg}\n")
    except OSError:
        pass


async def _tick(session: AsyncSession) -> None:
    s = get_settings()
    iface = os.environ.get("BANDWIDTH_NET_IFACE", s.daemon_net_interface)
    wg_if = os.environ.get("BANDWIDTH_WG_IFACE", s.daemon_wg_interface)

    sample0 = read_proc_net_dev(iface)
    await asyncio.sleep(1.0)
    sample1 = read_proc_net_dev(iface)
    mbps = 0.0
    if sample0 and sample1:
        drx = max(0, sample1[0] - sample0[0])
        dtx = max(0, sample1[1] - sample0[1])
        mbps = (drx + dtx) * 8 / 1_000_000

    cpu = 0.0
    try:
        import psutil

        cpu = float(psutil.cpu_percent(interval=None))
    except Exception:
        pass

    raw = await wg_show_dump(wg_if)
    peers = parse_wg_dump(raw)
    now_ts = int(time.time())

    r = await session.execute(
        select(VpnKey.wg_peer_public_key, VpnKey.user_id).where(
            VpnKey.is_active.is_(True),
            VpnKey.wg_peer_public_key.isnot(None),
        )
    )
    peer_user = {a: int(b) for a, b in r.all() if a}

    active_uids: set[int] = set()
    active_ips: list[str] = []
    for p in peers:
        hs = int(p.get("handshake") or 0)
        if hs and (now_ts - hs) <= WG_ACTIVE_HANDSHAKE_SEC:
            uid = peer_user.get(str(p["public_key"]))
            if uid is not None:
                active_uids.add(uid)
                # extract IP from allowed_ips
                ip = str(p.get("allowed_ips", "")).split(",")[0].split("/")[0].strip()
                if ip:
                    active_ips.append(ip)

    n = len(active_uids)
    fair = mbps > BANDWIDTH_FAIR_SHARE_THRESHOLD_MBPS or cpu > CPU_FAIR_SHARE_PERCENT
    if fair and n > 0:
        per_user = max(1, BANDWIDTH_FAIR_SHARE_POOL_MBPS // n)
    else:
        per_user = BANDWIDTH_MAX_PER_USER_MBPS

    for uid in active_uids:
        row = await session.scalar(select(UserLimit).where(UserLimit.user_id == uid))
        if row:
            # Меньше лишних UPDATE → меньше конкуренции за SQLite.
            if row.limit_mbps != per_user or row.fair_share_active != fair:
                row.limit_mbps = per_user
                row.fair_share_active = fair
                row.updated_at = datetime.now(UTC)
        else:
            session.add(
                UserLimit(
                    user_id=uid,
                    limit_mbps=per_user,
                    fair_share_active=fair,
                    updated_at=datetime.now(UTC),
                )
            )

    summary = (
        f"net~{mbps:.0f}Mbit/s cpu={cpu:.1f}% fair_share={fair} active_users={n} "
        f"per_user={per_user}Mbit/s iface={iface}/{wg_if}"
    )
    _append_log(s.bandwidth_guard_log, summary)
    logger.info(summary)
    if fair and n > 0:
        _append_log(
            s.bandwidth_guard_log,
            f"Активирован fair-share: {n} юзеров → по {per_user} Мбит/с",
        )

    apply_tc = os.environ.get("BANDWIDTH_TC_APPLY", "").lower() in ("1", "true", "yes")
    # If using Docker container for WG, we need to run tc inside it
    ctr = os.environ.get("AWG_DOCKER_CONTAINER", s.awg_docker_container).strip()
    ctr2 = (s.awg2_docker_container or "").strip()
    if apply_tc:
        if not fair or n == 0:
            cmd = f"tc qdisc del dev {wg_if} root 2>/dev/null || true"
        else:
            ips_str = " ".join(active_ips)
            cmd = f"""
tc qdisc del dev {wg_if} root 2>/dev/null || true
tc qdisc add dev {wg_if} root handle 1: htb default 10
tc class add dev {wg_if} parent 1: classid 1:1 htb rate {per_user}mbit
tc class add dev {wg_if} parent 1: classid 1:10 htb rate 1000mbit
for IP in {ips_str}; do
    tc filter add dev {wg_if} protocol ip parent 1:0 u32 match ip dst $IP flowid 1:1
done
"""
        if ctr:
            subprocess.run(["docker", "exec", ctr, "sh", "-c", cmd], check=False)
        if ctr2:
            subprocess.run(["docker", "exec", ctr2, "sh", "-c", cmd], check=False)
        if not ctr and not ctr2 and os.geteuid() == 0:
            subprocess.run(["sh", "-c", cmd], check=False)


async def run_loop() -> None:
    logging.basicConfig(level=logging.INFO)
    await init_db()
    while True:
        try:
            async with async_session_maker() as session:
                try:
                    await _tick(session)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("bandwidth_guard tick")
        await asyncio.sleep(30)


def main() -> None:
    asyncio.run(run_loop())


if __name__ == "__main__":
    main()
