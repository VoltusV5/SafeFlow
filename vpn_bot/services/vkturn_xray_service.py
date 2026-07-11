from __future__ import annotations

import re
import subprocess
import json
import time
import uuid
from pathlib import Path

from vpn_bot.config import get_settings
from vpn_bot.exceptions import ContainerIssueError
from vpn_bot.services.amnezia_protocols import issue_wireguard_client_conf_text

_VKTURN_PROXY_CONTAINER = "vpn-vk-turn-proxy"
_VKTURN_XRAY_CONTAINER = "vpn-vkturn-xray"
_VKTURN_XRAY_CONFIG_PATH = Path("/root/vpn-telegram-bot/deploy/vkturn-xray/config.json")


def _run(cmd: list[str], *, timeout: int = 30) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        raise ContainerIssueError(err[:700] or f"command failed: {' '.join(cmd)}")
    return (p.stdout or "").strip()


def _resolve_host() -> str:
    s = get_settings()
    ph = (s.public_host or "").strip()
    if ph:
        return ph
    ep = (s.wg_endpoint or "").strip()
    if not ep:
        raise ContainerIssueError("Не задан PUBLIC_HOST / WG_ENDPOINT")
    if "]:" in ep:
        return ep.split("]:", 1)[0].lstrip("[")
    if ep.count(":") > 1 and "[" in ep:
        return ep.split("]", 1)[0].lstrip("[")
    return ep.rsplit(":", 1)[0].strip() if ":" in ep else ep


def build_vkturn_wireguard_command(vk_link: str) -> tuple[str, str, str]:
    """Возвращает короткую команду запуска client для WireGuard-режима."""
    status = _run(
        ["docker", "inspect", "-f", "{{.State.Status}}", _VKTURN_PROXY_CONTAINER],
        timeout=20,
    )
    if status != "running":
        raise ContainerIssueError(
            f"vk-turn-proxy контейнер не запущен: {_VKTURN_PROXY_CONTAINER} ({status})"
        )
    host = _resolve_host()
    peer = f"{host}:56000"
    cmd = f'-peer {peer} -vk-link "{vk_link}" -listen 127.0.0.1:9000 -n 1'
    return host, peer, cmd


def build_vkturn_wireguard_conf() -> str:
    """Генерирует WG-конфиг и адаптирует его под локальный Termux vk-turn endpoint."""
    s = get_settings()
    raw = issue_wireguard_client_conf_text(s)
    lines = raw.splitlines()
    out: list[str] = []
    has_mtu = False
    for line in lines:
        if line.startswith("Endpoint = "):
            out.append("Endpoint = 127.0.0.1:9000")
            continue
        if line.startswith("MTU = "):
            has_mtu = True
        out.append(line)
        if line.strip() == "[Interface]" and not has_mtu:
            out.append("MTU = 1280")
            has_mtu = True
    text = "\n".join(out).strip() + "\n"
    # Безопасная нормализация на случай дублей при будущих правках.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def build_vkturn_vless_bundle(vk_link: str) -> tuple[str, str, str, str]:
    """Добавляет UUID в локальный Xray и возвращает команды для Termux/VLESS-клиента."""
    status = _run(
        ["docker", "inspect", "-f", "{{.State.Status}}", _VKTURN_XRAY_CONTAINER],
        timeout=20,
    )
    if status != "running":
        raise ContainerIssueError(
            f"vkturn-xray контейнер не запущен: {_VKTURN_XRAY_CONTAINER} ({status})"
        )
    if not _VKTURN_XRAY_CONFIG_PATH.exists():
        raise ContainerIssueError(f"Файл конфига не найден: {_VKTURN_XRAY_CONFIG_PATH}")

    with open(_VKTURN_XRAY_CONFIG_PATH, "r", encoding="utf-8") as f:
        doc = json.load(f)
    inbounds = doc.get("inbounds", [])
    if not inbounds:
        raise ContainerIssueError("vkturn-xray: отсутствуют inbounds в config.json")
    settings = inbounds[0].setdefault("settings", {})
    clients = settings.setdefault("clients", [])
    uid = str(uuid.uuid4())
    clients.append({"id": uid, "level": 0, "email": f"vkturn-{uid[:8]}@vpn.local"})

    with open(_VKTURN_XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    _run(
        ["docker", "exec", _VKTURN_XRAY_CONTAINER, "xray", "-test", "-config", "/etc/xray/config.json"],
        timeout=30,
    )
    subprocess.run(["docker", "restart", _VKTURN_XRAY_CONTAINER], check=False)
    time.sleep(1)

    host = _resolve_host()
    peer = f"{host}:56000"
    termux_cmd = f'-peer {peer} -vk-link "{vk_link}" -listen 127.0.0.1:9000 -vless -n 1'
    # For Happ/v2RayTun import on same phone (local vk-turn endpoint)
    local_vless = f"vless://{uid}@127.0.0.1:9000?type=tcp&security=none&encryption=none#vk-turn-local-vless"
    return host, peer, termux_cmd, local_vless
