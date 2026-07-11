"""Запуск wg show … dump на хосте или через docker exec (Amnezia AWG в контейнере)."""

from __future__ import annotations

import asyncio
import logging

from vpn_bot.config import get_settings

logger = logging.getLogger(__name__)


def _wg_dump_peer_lines(raw: str) -> list[str]:
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    if len(lines) <= 1:
        return []
    return lines[1:]


async def _wg_dump_from_docker(container: str, ifname: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        container,
        "wg",
        "show",
        ifname,
        "dump",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            "wg show %s %s dump failed: %s",
            container,
            ifname,
            (err or b"").decode(errors="replace")[:200],
        )
        return ""
    return out.decode(errors="replace")


async def wg_show_dump(iface: str) -> str:
    s = get_settings()
    ctr = (s.awg_docker_container or "").strip()
    ctr2 = (s.awg2_docker_container or "").strip()
    if2 = (s.awg2_wg_iface or iface).strip() or iface

    if ctr or ctr2:
        peer_lines: list[str] = []
        if ctr:
            peer_lines.extend(_wg_dump_peer_lines(await _wg_dump_from_docker(ctr, iface)))
        if ctr2:
            peer_lines.extend(_wg_dump_peer_lines(await _wg_dump_from_docker(ctr2, if2)))
        if not peer_lines:
            return ""
        # parse_wg_dump пропускает только первую строку — подставляем фиктивную строку интерфейса.
        return "iface\t0\t0\t0\t0\t0\t0\t0\n" + "\n".join(peer_lines)

    proc = await asyncio.create_subprocess_exec(
        "wg",
        "show",
        iface,
        "dump",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(
            "wg show %s dump failed: %s",
            iface,
            (err or b"").decode(errors="replace")[:200],
        )
        return ""
    return out.decode(errors="replace")
