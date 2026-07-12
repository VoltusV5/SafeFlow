from __future__ import annotations

import base64
import json
import secrets
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import quote

from vpn_bot.config import Settings, get_settings
from vpn_bot.exceptions import ContainerIssueError

_CLEAN_XRAY_CONFIG_PATH = Path("/root/vpn-telegram-bot/deploy/clean-xray/config.json")  # noqa: E501


def _run(cmd: list[str], *, timeout: int = 60) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: E501
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "").strip()
        raise ContainerIssueError(err[:700] or f"command failed: {' '.join(cmd)}")  # noqa: E501
    return (p.stdout or "").strip()


def _resolve_host() -> str:
    s = get_settings()
    h = (s.clean_xray_host or "").strip()
    if h:
        return h
    ph = (s.public_host or "").strip()
    if ph:
        return ph
    ep = (s.wg_endpoint or "").strip()
    if not ep:
        raise ContainerIssueError("Не задан CLEAN_XRAY_HOST / PUBLIC_HOST / WG_ENDPOINT")  # noqa: E501
    if "]:" in ep:
        return ep.split("]:", 1)[0].lstrip("[")
    if ep.count(":") > 1 and "[" in ep:
        return ep.split("]", 1)[0].lstrip("[")
    return ep.rsplit(":", 1)[0].strip() if ":" in ep else ep


def _ensure_container_running() -> str:
    s = get_settings()
    ctr = (s.clean_xray_container or "vpn-clean-xray").strip()
    status = _run(["docker", "inspect", "-f", "{{.State.Status}}", ctr], timeout=30)  # noqa: E501
    if status != "running":
        raise ContainerIssueError(f"clean-xray контейнер не запущен: {ctr} ({status})")  # noqa: E501
    return ctr


def _add_user_to_config(inbound_tag: str, client_obj: dict) -> None:
    ctr = _ensure_container_running()
      # noqa: W293, E114, E116
    with open(_CLEAN_XRAY_CONFIG_PATH, "r", encoding="utf-8") as f:
        doc = json.load(f)
      # noqa: W293, E114
    inbound = None
    for ib in doc.get("inbounds", []):
        if ib.get("tag") == inbound_tag:
            inbound = ib
            break
              # noqa: W293, E114, E116
    if not inbound:
        raise ContainerIssueError(f"Inbound {inbound_tag} не найден в config.json")  # noqa: E501
          # noqa: W293, E114, E116
    settings = inbound.setdefault("settings", {})
    clients = settings.setdefault("clients", [])
    clients.append(client_obj)
      # noqa: W293, E114, E116
    new_json = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    with open(_CLEAN_XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(new_json)
          # noqa: W293, E114, E116
    # Validate using a temporary container or the running one if it has xray binary  # noqa: E501
    # We can just use the running one: docker exec vpn-clean-xray xray -test -config /etc/xray/config.json  # noqa: E501
    val = subprocess.run(["docker", "exec", ctr, "xray", "-test", "-config", "/etc/xray/config.json"], capture_output=True)  # noqa: E501
    if val.returncode != 0:
        raise ContainerIssueError(f"Ошибка валидации конфига: {val.stderr.decode()[:200]}")  # noqa: E501
          # noqa: W293, E114, E116
    # Reload via SIGHUP
    subprocess.run(["docker", "restart", ctr], check=False)
    time.sleep(1)


def _get_reality_params(s: Settings) -> tuple[str, str, str]:
    pbk = (s.clean_xray_reality_public_key or "").strip()
    sid = (s.clean_xray_reality_short_id or "").strip()
    sni = (s.clean_xray_reality_server_name or "ok.ru").strip()
    if not pbk or not sid:
        raise ContainerIssueError(
            "Для REALITY задайте CLEAN_XRAY_REALITY_PUBLIC_KEY и CLEAN_XRAY_REALITY_SHORT_ID"  # noqa: E501
        )
    return pbk, sid, sni


def _build_reality_query(pbk: str, sid: str, sni: str) -> str:
    return f"security=reality&pbk={quote(pbk)}&sni={quote(sni)}&sid={quote(sid)}&fp=chrome"  # noqa: E501


def _remove_reality_from_config(inbound_tag: str) -> None:
    """Helper to ensure the inbound has NO REALITY (for VMess if it breaks clients)."""  # noqa: E501
    ctr = _ensure_container_running()
      # noqa: W293, E114, E116
    with open(_CLEAN_XRAY_CONFIG_PATH, "r", encoding="utf-8") as f:
        doc = json.load(f)
      # noqa: W293, E114
    changed = False
    for ib in doc.get("inbounds", []):
        if ib.get("tag") == inbound_tag:
            ss = ib.get("streamSettings", {})
            if ss.get("security") == "reality":
                ib["streamSettings"] = {
                    "network": "tcp",
                    "security": "none"
                }
                changed = True
            break
              # noqa: W293, E114, E116
    if changed:
        new_json = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        with open(_CLEAN_XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_json)
        subprocess.run(["docker", "restart", ctr], check=False)
        time.sleep(1)


def _ensure_reality_in_config(inbound_tag: str, pbk: str, sid: str, sni: str) -> None:  # noqa: E501
    """Helper to ensure the inbound has REALITY enabled in config.json (for Trojan/VMess)."""  # noqa: E501
    ctr = _ensure_container_running()
      # noqa: W293, E114, E116
    with open(_CLEAN_XRAY_CONFIG_PATH, "r", encoding="utf-8") as f:
        doc = json.load(f)
      # noqa: W293, E114
    changed = False
    for ib in doc.get("inbounds", []):
        if ib.get("tag") == inbound_tag:
            ss = ib.get("streamSettings", {})
            if ss.get("security") != "reality":
                vless_ib = next((x for x in doc["inbounds"] if x.get("tag") == "in-vless"), None)  # noqa: E501
                priv_key = vless_ib["streamSettings"]["realitySettings"]["privateKey"]  # noqa: E501
                  # noqa: W293, E114, E116
                ib["streamSettings"] = {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": f"{sni}:443",
                        "xver": 0,
                        "serverNames": [sni, "www.cloudflare.com"],
                        "privateKey": priv_key,
                        "shortIds": [sid]
                    }
                }
                changed = True
            break
              # noqa: W293, E114, E116
    if changed:
        new_json = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        with open(_CLEAN_XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_json)
        subprocess.run(["docker", "restart", ctr], check=False)
        time.sleep(1)


def _ensure_reality_in_config(inbound_tag: str, pbk: str, sid: str, sni: str) -> None:  # noqa: E501
    """Helper to ensure the inbound has REALITY enabled in config.json (for Trojan/VMess)."""  # noqa: E501
    ctr = _ensure_container_running()
      # noqa: W293, E114, E116
    with open(_CLEAN_XRAY_CONFIG_PATH, "r", encoding="utf-8") as f:
        doc = json.load(f)
      # noqa: W293, E114
    changed = False
    for ib in doc.get("inbounds", []):
        if ib.get("tag") == inbound_tag:
            ss = ib.get("streamSettings", {})
            if ss.get("security") != "reality":
                vless_ib = next((x for x in doc["inbounds"] if x.get("tag") == "in-vless"), None)  # noqa: E501
                priv_key = vless_ib["streamSettings"]["realitySettings"]["privateKey"]  # noqa: E501
                  # noqa: W293, E114, E116
                ib["streamSettings"] = {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "dest": f"{sni}:443",
                        "xver": 0,
                        "serverNames": [sni, "www.cloudflare.com"],
                        "privateKey": priv_key,
                        "shortIds": [sid]
                    }
                }
                changed = True
            break
              # noqa: W293, E114, E116
    if changed:
        new_json = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        with open(_CLEAN_XRAY_CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write(new_json)
        subprocess.run(["docker", "restart", ctr], check=False)
        time.sleep(1)


def issue_clean_xray_vless_url() -> tuple[str, str]:
    s = get_settings()
    host = _resolve_host()
    uid = str(uuid.uuid4())
    email = f"vless-{uid[:8]}@vpn.local"
    _add_user_to_config(
        "in-vless",
        {
            "id": uid,
            "flow": "xtls-rprx-vision",
            "email": email,
        },
    )
    pbk, sid, sni = _get_reality_params(s)
    rq = _build_reality_query(pbk, sid, sni)
    url = (
        f"vless://{uid}@{host}:{int(s.clean_xray_port_vless)}"
        f"?type=tcp&encryption=none&flow=xtls-rprx-vision&{rq}#SafeFlow-VLESS"
    )
    return "xray_vless.txt", url


def issue_clean_xray_trojan_url() -> tuple[str, str]:
    s = get_settings()
    host = _resolve_host()
    pwd = secrets.token_urlsafe(16)
    email = f"trojan-{uuid.uuid4().hex[:8]}@vpn.local"
      # noqa: W293, E114, E116
    pbk, sid, sni = _get_reality_params(s)
    _ensure_reality_in_config("in-trojan", pbk, sid, sni)
      # noqa: W293, E114, E116
    _add_user_to_config(
        "in-trojan",
        {
            "password": pwd,
            "email": email,
        },
    )
    rq = _build_reality_query(pbk, sid, sni)
    url = (
        f"trojan://{quote(pwd)}@{host}:{int(s.clean_xray_port_trojan)}"
        f"?type=tcp&{rq}#SafeFlow-Trojan"
    )
    return "xray_trojan.txt", url


def issue_clean_xray_vmess_url() -> tuple[str, str]:
    s = get_settings()
    host = _resolve_host()
    uid = str(uuid.uuid4())
    email = f"vmess-{uid[:8]}@vpn.local"
      # noqa: W293, E114, E116
    _remove_reality_from_config("in-vmess")
      # noqa: W293, E114, E116
    _add_user_to_config(
        "in-vmess",
        {
            "id": uid,
            "alterId": 0,
            "email": email,
        },
    )
    vmess_obj = {
        "v": "2",
        "ps": "SafeFlow-VMess",
        "add": host,
        "port": str(int(s.clean_xray_port_vmess)),
        "id": uid,
        "aid": "0",
        "net": "tcp",
        "type": "none",
        "host": "",
        "tls": "",
        "sni": "",
        "alpn": "",
        "fp": "",
    }
    raw = json.dumps(vmess_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")  # noqa: E501
    url = "vmess://" + base64.b64encode(raw).decode("ascii")
    return "xray_vmess.txt", url


def issue_clean_xray_ss_url() -> tuple[str, str]:
    s = get_settings()
    host = _resolve_host()
    method = (s.clean_xray_ss_method or "chacha20-ietf-poly1305").strip()
    pwd = secrets.token_urlsafe(16)
    email = f"ss-{uuid.uuid4().hex[:8]}@vpn.local"
      # noqa: W293, E114, E116
    # Shadowsocks over REALITY is not widely supported by standard ss:// URIs.
    # We leave it as raw TCP, which is standard for Shadowsocks.
    _add_user_to_config(
        "in-ss",
        {
            "method": method,
            "password": pwd,
            "email": email,
        },
    )
      # noqa: W293, E114, E116
    # Base64 encode the entire connection string to hide IP/port in the text
    # WAIT! Standard SIP002 requires base64(method:password)@host:port
    userinfo = base64.urlsafe_b64encode(f"{method}:{pwd}".encode("utf-8")).decode("ascii").rstrip("=")  # noqa: E501
    url = f"ss://{userinfo}@{host}:{int(s.clean_xray_port_shadowsocks)}#SafeFlow-Shadowsocks"  # noqa: E501
    return "xray_shadowsocks.txt", url  # noqa: W292
