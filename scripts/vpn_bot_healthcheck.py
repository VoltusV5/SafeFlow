#!/usr/bin/env python3
"""Проверка здоровья: systemd, Docker (основные контейнеры), PRAGMA integrity_check для SQLite."""  # noqa: E501

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# Запуск `python scripts/vpn_bot_healthcheck.py` из любого каталога: корень проекта в PYTHONPATH и .env  # noqa: E501
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from vpn_bot.config import get_settings  # noqa: E402
from vpn_bot.utils.admin_notify import send_message_to_admins  # noqa: E402
from vpn_bot.utils.sqlite_backup import resolve_sqlite_path  # noqa: E402
from vpn_bot.wg_utils import parse_wg_dump  # noqa: E402

_DEFAULT_UNITS = "vpn-bot.service,vpn-bot-traffic-logger.service,vpn-bot-bandwidth-guard.service"  # noqa: E501

# Ожидаемые Docker-контейнеры (статус running). Список можно переопределить в .env:  # noqa: E501
# VPN_BOT_HEALTHCHECK_CONTAINERS=name1,name2,...
_DEFAULT_CONTAINERS = (
    "vpn-telegram-mtg,vpn-telegram-mtg-alt1,vpn-telegram-mtg-alt2,"
    "vpn-telegram-socks5,vpn-telegram-socks5-alt1,vpn-telegram-socks5-alt2,"
    "vpn-telegram-http-proxy,vpn-clean-xray,"
    "amnezia-awg,amnezia-awg-20,amnezia-wireguard,amnezia-openvpn,amnezia-openvpn-cloak,"  # noqa: E501
    "amnezia-shadowsocks,amnezia-ipsec,amnezia-xray"
)

# Мягкая проверка WG внутри контейнера (только чтение `wg show … dump`, трафик не трогаем).  # noqa: E501
_DEFAULT_WG_TARGETS = (
    "amnezia-awg:wg0,amnezia-awg-20:wg0,amnezia-wireguard:wg0"  # noqa: E501
)
_WG_COOLDOWN_FILE = _PROJECT_ROOT / ".vpn_healthcheck_wg_cooldown.json"


def _wg_cooldown_get(key: str) -> float:
    try:
        raw = _WG_COOLDOWN_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        return float(data.get(key, 0.0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0.0


def _wg_cooldown_set(key: str, ts: float) -> None:
    try:
        data: dict[str, float] = {}
        if _WG_COOLDOWN_FILE.is_file():
            data = json.loads(_WG_COOLDOWN_FILE.read_text(encoding="utf-8"))
        data[key] = ts
        _WG_COOLDOWN_FILE.write_text(
            json.dumps(data, indent=0), encoding="utf-8"
        )  # noqa: E501
    except OSError as e:
        print(
            f"vpn_bot_healthcheck: cannot write wg cooldown: {e}", file=sys.stderr
        )  # noqa: E501


def _docker_wg_dump(
    container: str, iface: str, timeout: float = 15.0, auto_recover: bool = True
) -> tuple[str, str | None]:  # noqa: E501
    r = subprocess.run(
        ["docker", "exec", container, "wg", "show", iface, "dump"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:400]
        if auto_recover and (
            "No such device" in err or "Unable to access interface" in err
        ):  # noqa: E501
            print(f"Auto-recovering {container}:{iface} ...", file=sys.stderr)
            conf_path = (
                "/opt/amnezia/awg/wg0.conf"
                if "awg" in container
                else "/opt/amnezia/wireguard/wg0.conf"
            )  # noqa: E501
            rec = subprocess.run(
                ["docker", "exec", container, "wg-quick", "up", conf_path],
                capture_output=True,
                text=True,
            )  # noqa: E501
            if rec.returncode == 0:
                print(
                    f"Auto-recovery for {container}:{iface} successful.",
                    file=sys.stderr,
                )  # noqa: E501
                try:
                    from vpn_bot.utils.admin_notify import send_message_to_admins

                    send_message_to_admins(
                        f"🛠 VPN bot: Автоматически восстановлен упавший интерфейс {iface} в контейнере {container}."
                    )  # noqa: E501
                except Exception as e:
                    print(f"Failed to notify admins: {e}", file=sys.stderr)
                return _docker_wg_dump(
                    container, iface, timeout, auto_recover=False
                )  # noqa: E501
            else:
                err += f" | Auto-recovery wg-quick up failed: {(rec.stderr or rec.stdout).strip()[:200]}"  # noqa: E501
        return (
            "",
            f"docker exec {container} wg show {iface} dump: ошибка ({err or 'non-zero exit'})",
        )  # noqa: E501
    out = (r.stdout or "").strip()
    if not out:
        return (
            "",
            f"{container} {iface}: пустой вывод wg dump (интерфейс не поднят?)",
        )  # noqa: E501
    return out, None


def _check_wg_handshake_staleness(
    container: str,
    iface: str,
    *,
    stale_sec: int,
    min_peers: int,
    cooldown_min: int,
) -> str | None:
    """Чтение wg dump; при ошибке exec или если все недавние handshake протухли — алерт (с cooldown)."""  # noqa: E501
    key = f"{container}:{iface}"
    cd_sec = max(60, cooldown_min * 60)
    raw, err = _docker_wg_dump(container, iface)
    if err:
        msg = err
    else:
        peers = parse_wg_dump(raw + "\n")
        with_hs = [p for p in peers if int(p["handshake"]) > 0]
        if len(with_hs) < min_peers:
            return None
        now = int(time.time())
        newest_hs_age = min(now - int(p["handshake"]) for p in with_hs)
        if newest_hs_age <= stale_sec:
            return None
        msg = (
            f"{container} ({iface}): у {len(with_hs)} peer'ов с handshake нет обновления дольше "  # noqa: E501
            f"{stale_sec // 60} мин (самый свежий ~{newest_hs_age // 60} мин назад). "  # noqa: E501
            f"Похоже на зависание или недоступность туннеля."
        )
    if time.time() - _wg_cooldown_get(key) < cd_sec:
        return None
    _wg_cooldown_set(key, time.time())
    return msg


def _check_docker_container(name: str) -> str | None:
    r = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Status}}", name],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:300]
        return f"docker {name}: контейнер недоступен ({err or 'docker inspect failed'})"  # noqa: E501
    status = (r.stdout or "").strip()
    if status != "running":
        return f"docker {name}: статус {status!r} (ожидался running)"
    return None


def _check_unit(name: str) -> str | None:
    r = subprocess.run(
        ["systemctl", "is-active", name],
        capture_output=True,
        text=True,
    )
    line = (r.stdout or "").strip()
    if line != "active":
        return f"{name}: {line or r.stderr.strip() or 'not active'}"
    return None


def _check_sqlite(path: Path | None, label: str) -> str | None:
    if path is None:
        return f"{label}: URL не SQLite"
    if not path.is_file():
        return f"{label}: файл не найден: {path}"
    conn = sqlite3.connect(str(path), timeout=30.0)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            return f"{label}: integrity_check={row!r}"
    finally:
        conn.close()
    return None


def collect_errors(
    *, skip_systemd: bool, skip_docker: bool
) -> list[str]:  # noqa: C901, E501
    errs: list[str] = []
    if not skip_systemd:
        units_raw = os.environ.get("VPN_BOT_HEALTHCHECK_UNITS", _DEFAULT_UNITS)
        for u in [x.strip() for x in units_raw.split(",") if x.strip()]:
            msg = _check_unit(u)
            if msg:
                errs.append(msg)
    if not skip_docker:
        containers_raw = os.environ.get(
            "VPN_BOT_HEALTHCHECK_CONTAINERS", _DEFAULT_CONTAINERS
        )  # noqa: E501
        for c in [x.strip() for x in containers_raw.split(",") if x.strip()]:
            msg = _check_docker_container(c)
            if msg:
                errs.append(msg)

        if os.environ.get(
            "VPN_BOT_HEALTHCHECK_SKIP_WG", ""
        ).strip().lower() not in (  # noqa: E501
            "1",
            "true",
            "yes",
        ):
            stale_sec = int(
                os.environ.get("VPN_BOT_HEALTHCHECK_WG_STALE_SEC", "600")
            )  # noqa: E501
            min_peers = int(
                os.environ.get("VPN_BOT_HEALTHCHECK_WG_MIN_PEERS", "3")
            )  # noqa: E501
            cooldown_min = int(
                os.environ.get("VPN_BOT_HEALTHCHECK_WG_COOLDOWN_MIN", "30")
            )  # noqa: E501
            targets_raw = os.environ.get(
                "VPN_BOT_HEALTHCHECK_WG_TARGETS", _DEFAULT_WG_TARGETS
            )
            for t in [x.strip() for x in targets_raw.split(",") if x.strip()]:
                if ":" not in t:
                    continue
                ctr, iface = t.split(":", 1)
                ctr, iface = ctr.strip(), iface.strip()
                if not ctr or not iface:
                    continue
                msg = _check_wg_handshake_staleness(
                    ctr,
                    iface,
                    stale_sec=stale_sec,
                    min_peers=min_peers,
                    cooldown_min=cooldown_min,
                )
                if msg:
                    errs.append(msg)
    s = get_settings()
    for label, p in (
        ("DATABASE_URL", resolve_sqlite_path(s.database_url)),
        (
            "ANALYTICS_DATABASE_URL",
            resolve_sqlite_path(s.analytics_database_url),
        ),  # noqa: E501
    ):
        msg = _check_sqlite(p, label)
        if msg:
            errs.append(msg)
    return errs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-systemd",
        action="store_true",
        help="Не проверять systemctl (удобно на dev-машине без этих юнитов).",
    )
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Не проверять docker контейнеры (dev или без Docker).",
    )
    parser.add_argument(
        "--notify-admins",
        action="store_true",
        help="При ошибках отправить сообщение админам (ADMIN_IDS) этим же ботом.",  # noqa: E501
    )
    args = parser.parse_args()
    os.chdir(_PROJECT_ROOT)
    errs = collect_errors(
        skip_systemd=args.skip_systemd,
        skip_docker=args.skip_docker,
    )
    if errs:
        body = "\n".join(errs)
        print(body, file=sys.stderr)
        if args.notify_admins:
            send_message_to_admins("⚠️ VPN bot: healthcheck не прошёл\n\n" + body)
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
