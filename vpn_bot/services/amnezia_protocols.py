"""Выдача vpn:// для протоколов Amnezia через Docker (без удаления существующих клиентов)."""  # noqa: E501

from __future__ import annotations

import base64
import fcntl
import json
import re
import secrets
import string
import subprocess
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from vpn_bot.amnezia_vpn_url import (
    amnezia_awg_conf_to_vpn_url,
    build_awg_last_config_object,
    protocols_document_to_vpn_url,
)
from vpn_bot.config import Settings
from vpn_bot.enums import VpnProtocol
from vpn_bot.exceptions import ContainerIssueError
from vpn_bot.services.keygen import _FILE_STEM


def _fname(p: VpnProtocol) -> str:
    return f"{_FILE_STEM[p]}.txt"


def _public_host(s: Settings) -> str:
    ph = (s.public_host or "").strip()
    if ph:
        return ph
    ep = (s.wg_endpoint or "").strip()
    if not ep:
        raise ContainerIssueError("Задайте WG_ENDPOINT или PUBLIC_HOST")
    if "]:" in ep:
        return ep.split("]:", 1)[0].lstrip("[")
    if ep.count(":") > 1 and "[" in ep:
        return ep.split("]", 1)[0].lstrip("[")
    return ep.rsplit(":", 1)[0].strip() if ":" in ep else ep


def _dns_pair(s: Settings) -> tuple[str, str]:
    d1 = (s.wg_client_dns or "1.1.1.1").strip() or "1.1.1.1"
    d2 = (s.wg_share_dns2 or "1.0.0.1").strip() or "1.0.0.1"
    return d1, d2


def _desc(s: Settings) -> str:
    return (s.amnezia_share_description or "SafeFlow").strip() or "SafeFlow"


def _run(
    cmd: list[str], *, input_bytes: bytes | None = None, timeout: int = 180
) -> str:  # noqa: E501
    r = subprocess.run(
        cmd,
        capture_output=True,
        input=input_bytes,
        timeout=timeout,
        check=False,
    )
    if r.returncode != 0:
        err = (r.stderr or b"").decode("utf-8", errors="replace")[:900]
        raise ContainerIssueError(err or f"код выхода {r.returncode}")
    return (r.stdout or b"").decode("utf-8", errors="replace")


def _dex_sh(container: str, script: str, *, timeout: int = 180) -> str:
    return _run(
        ["docker", "exec", container, "sh", "-c", script], timeout=timeout
    )  # noqa: E501


def _dex_cat_bin(container: str, path: str) -> bytes:
    r = subprocess.run(
        ["docker", "exec", container, "cat", path],
        capture_output=True,
        timeout=90,
        check=False,
    )
    if r.returncode != 0:
        raise ContainerIssueError(
            (r.stderr or b"").decode(errors="replace")[:400]
            or f"нет файла {path}"  # noqa: E501
        )
    return r.stdout


def _write_container_path(container: str, path: str, data: bytes) -> None:
    r = subprocess.run(
        ["docker", "exec", "-i", container, "sh", "-c", f"cat > {path}"],
        input=data,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if r.returncode != 0:
        raise ContainerIssueError(
            (r.stderr or b"").decode(errors="replace")[:500]
            or "запись в контейнер не удалась"  # noqa: E501
        )


def _validate_xray_config(container: str, path: str) -> None:
    """Проверка синтаксиса/валидности xray-конфига внутри контейнера."""
    _dex_sh(
        container,
        (
            f"xray -test -config '{path}' >/dev/null 2>&1 "
            f"|| xray run -test -config '{path}' >/dev/null 2>&1"
        ),
        timeout=90,
    )


def _send_xray_hup(container: str) -> None:
    """Мягкий reload Xray без рестарта контейнера."""
    _dex_sh(container, "killall -HUP xray", timeout=30)


def _verify_xray_inbound_listening(
    container: str, port: int, *, timeout_sec: int = 12
) -> None:  # noqa: E501
    """
    Проверяет, что Xray слушает нужный TCP-порт внутри контейнера.
    Смотрим /proc/net/tcp{,6}: state=0A (LISTEN), local_port == port.
    """
    if port < 1 or port > 65535:
        raise ContainerIssueError(f"Некорректный порт Xray: {port}")
    script = f"""
set -eu
PHEX="$(printf '%04X' {port})"
awk -v p="$PHEX" '
  FNR==1 {{ next }}
  {{
    split($2, a, ":")
    if (toupper(a[2]) == p && $4 == "0A") {{
      found = 1
    }}
  }}
  END {{ exit(found ? 0 : 1) }}
' /proc/net/tcp /proc/net/tcp6
"""
    deadline = time.time() + max(1, timeout_sec)
    last_err = ""
    while time.time() < deadline:
        try:
            _dex_sh(container, script, timeout=15)
            return
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            time.sleep(1)
    raise ContainerIssueError(
        f"Xray не слушает порт {port} после reload: {last_err[:200]}"
    )


def _apply_xray_config_with_safe_reload(
    container: str, path: str, port: int, *, allow_fallback_restart: bool
) -> None:
    """
    write -> validate config -> HUP reload -> verify inbound.
    При ошибке делаем fallback: docker restart и повторную проверку.
    """
    try:
        _validate_xray_config(container, path)
        _send_xray_hup(container)
        _verify_xray_inbound_listening(container, port, timeout_sec=12)
    except Exception as e:  # noqa: BLE001, F841
        if not allow_fallback_restart:
            raise
        _run(["docker", "restart", container], timeout=180)
        time.sleep(4)
        try:
            _verify_xray_inbound_listening(container, port, timeout_sec=15)
        except Exception as e2:  # noqa: BLE001
            raise ContainerIssueError(
                "Xray reload не удался, fallback restart тоже не помог: "
                f"{str(e2)[:220]}"
            ) from e2
        # Не валим выдачу ключа, если fallback восстановил сервис.
        return


@contextmanager
def _flock(lock_name: str) -> None:
    root = Path("/root/vpn-telegram-bot")
    root.mkdir(parents=True, exist_ok=True)
    p = root / f".lock_amnezia_{lock_name}"
    with p.open("a+") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        yield


def _rand_id(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _provision_plain_wireguard_client(
    s: Settings,
) -> tuple[str, str, str, str]:
    """Новый peer на сервере + vpn://. Возвращает client_conf, client_pub, vpn_url, filename."""  # noqa: E501
    ctr = (s.docker_wireguard_container or "amnezia-wireguard").strip()
    conf = (s.wireguard_wg_conf or "/opt/amnezia/wireguard/wg0.conf").strip()
    iface = "wg0"
    prefix = (s.wireguard_client_prefix or "10.8.1").strip()
    host = _public_host(s)
    port = int(s.wireguard_endpoint_port)
    dns = (s.wg_client_dns or "1.1.1.1").strip() or "1.1.1.1"
    mtu = (s.awg_client_mtu or "1376").strip() or "1376"
    dns1, dns2 = _dns_pair(s)

    with _flock(f"wg_{ctr}"):
        psk = _dex_sh(
            ctr,
            f"grep -m1 '^PresharedKey' '{conf}' | sed 's/^PresharedKey = //'",
        ).strip()
        if not psk:
            raise ContainerIssueError("Не прочитан PresharedKey из wg0.conf")
        spub = _dex_sh(
            ctr, f"wg show {iface} | awk '/public key:/{{print $3}}'"
        ).strip()  # noqa: E501
        if not spub:
            raise ContainerIssueError("wg show: нет public key сервера")

        priv = _dex_sh(ctr, "wg genkey").strip().replace("\r", "")
        pub = (
            _run(
                ["docker", "exec", "-i", ctr, "wg", "pubkey"],
                input_bytes=(priv + "\n").encode(),
                timeout=60,
            )
            .strip()
            .replace("\r", "")
        )

        used_out = _dex_sh(
            ctr,
            "grep -oE 'AllowedIPs = "
            + re.escape(prefix)
            + r"\.[0-9]+/32' '"
            + conf
            + r"' | sed -n 's/.*\.\([0-9][0-9]*\)\/32/\1/p' | sort -n -u",
        )
        used = {x for x in used_out.split() if x.isdigit()}
        octet = None
        for i in range(2, 255):
            if str(i) not in used:
                octet = i
                break
        if octet is None:
            raise ContainerIssueError("Нет свободного IP в подсети WireGuard")

        addr = f"{prefix}.{octet}/32"
        client_conf = (
            f"[Interface]\n"
            f"PrivateKey = {priv}\n"
            f"Address = {addr}\n"
            f"DNS = {dns}\n\n"
            f"[Peer]\n"
            f"PublicKey = {spub}\n"
            f"PresharedKey = {psk}\n"
            f"Endpoint = {host}:{port}\n"
            f"AllowedIPs = 0.0.0.0/0, ::/0\n"
            f"PersistentKeepalive = 25\n"
        )

        _dex_sh(
            ctr,
            f"""
set -eu
CF='{conf}'
IF='{iface}'
cp "$CF" "${{CF}}.bak.vpn_bot"
if ! {{
  {{
    echo ""
    echo "[Peer]"
    echo "PublicKey = {pub}"
    echo "PresharedKey = {psk}"
    echo "AllowedIPs = {prefix}.{octet}/32"
  }} >> "$CF"
  wg-quick strip "$CF" > /tmp/wg.strip.vpn_bot
  wg syncconf "$IF" /tmp/wg.strip.vpn_bot
  rm -f /tmp/wg.strip.vpn_bot
}}; then
  cp "${{CF}}.bak.vpn_bot" "$CF"
  wg-quick strip "$CF" > /tmp/wg.strip.r
  wg syncconf "$IF" /tmp/wg.strip.r || true
  rm -f /tmp/wg.strip.r
  exit 1
fi
""",
            timeout=120,
        )

    inner = build_awg_last_config_object(client_conf, pub, mtu=mtu)
    vpn_url = protocols_document_to_vpn_url(
        container="amnezia-wireguard",
        protocol_last_config_objects={"wireguard": inner},
        host_name=host,
        dns1=dns1,
        dns2=dns2,
        description=_desc(s),
    )
    filename = _fname(VpnProtocol.WIREGUARD)
    return client_conf, pub, vpn_url, filename


def issue_wireguard_vpn_url(s: Settings) -> tuple[str, str, str]:
    """Plain WireGuard (amnezia-wireguard): peer + vpn://. Возвращает filename, vpn_url, client_pub."""  # noqa: E501
    _client_conf, pub, vpn_url, filename = _provision_plain_wireguard_client(s)
    return filename, vpn_url, pub


def issue_wireguard_client_conf_text(s: Settings) -> str:
    """Тот же новый peer, что и для vpn://, но только текст клиентского wg.conf."""  # noqa: E501
    client_conf, _pub, _vpn_url, _fn = _provision_plain_wireguard_client(s)
    return client_conf


def _normalize_pem_block(s: str) -> str:
    return "\n".join(
        line.rstrip()
        for line in s.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    ).strip()  # noqa: E501


def _build_openvpn_ovpn(
    *,
    remote_host: str,
    remote_port: int,
    proto: str,
    ca: str,
    cert: str,
    key: str,
    ta: str,
    dns1: str,
    dns2: str,
    socks_line: str,
    route_line: str,
) -> str:
    ca, cert, key, ta = (
        _normalize_pem_block(ca),
        _normalize_pem_block(cert),
        _normalize_pem_block(key),
        _normalize_pem_block(ta),
    )
    ta_block = f"<tls-auth>\n{ta}\n</tls-auth>\n" if ta else ""
    # Как у сервера Amnezia: data-ciphers + cipher (обязательно для OpenVPN 2.5+ при data-ciphers на сервере).  # noqa: E501
    # block-outside-dns убран — ломает подключение в части клиентов Amnezia на Android/iOS.  # noqa: E501
    return (
        "client\n"
        "dev tun\n"
        f"proto {proto}\n"
        "resolv-retry infinite\n"
        "nobind\n"
        "persist-key\n"
        "persist-tun\n"
        "cipher AES-256-GCM\n"
        "data-ciphers AES-256-GCM\n"
        "auth SHA512\n"
        "auth-nocache\n"
        "verb 3\n"
        "mute-replay-warnings\n"
        "tls-client\n"
        "tls-version-min 1.2\n"
        "key-direction 1\n"
        "remote-cert-tls server\n"
        "redirect-gateway def1 bypass-dhcp\n"
        f"dhcp-option DNS {dns1}\n"
        f"dhcp-option DNS {dns2}\n"
        f"{socks_line}"
        f"{route_line}"
        f"remote {remote_host} {remote_port}\n\n"
        "<ca>\n"
        f"{ca}\n"
        "</ca>\n"
        "<cert>\n"
        f"{cert}\n"
        "</cert>\n"
        "<key>\n"
        f"{key}\n"
        "</key>\n"
        f"{ta_block}"
    )


def _easyrsa_issue(
    container: str, client_id: str
) -> tuple[str, str, str, str]:  # noqa: E501
    base = "/opt/amnezia/openvpn"
    pki = f"{base}/pki"
    _dex_sh(
        container,
        f"EASYRSA_PKI={pki} /usr/share/easy-rsa/easyrsa "
        f"--batch build-client-full {client_id} nopass",
        timeout=300,
    )
    ca = _dex_cat_bin(container, f"{base}/ca.crt").decode(errors="replace")
    crt = _dex_cat_bin(container, f"{pki}/issued/{client_id}.crt").decode(
        errors="replace"
    )  # noqa: E501
    key = _dex_cat_bin(container, f"{pki}/private/{client_id}.key").decode(
        errors="replace"
    )  # noqa: E501
    ta = _dex_cat_bin(container, f"{base}/ta.key").decode(errors="replace")
    return ca, crt, key, ta


def issue_openvpn_vpn_url(s: Settings) -> tuple[str, str]:
    ctr = (s.docker_openvpn_container or "amnezia-openvpn").strip()
    host = _public_host(s)
    dns1, dns2 = _dns_pair(s)
    port = int(s.openvpn_tcp_port)
    client_id = _rand_id(16)
    with _flock(f"ovpn_{ctr}"):
        ca, crt, key, ta = _easyrsa_issue(ctr, client_id)
    ovpn = _build_openvpn_ovpn(
        remote_host=host,
        remote_port=port,
        proto="tcp",
        ca=ca,
        cert=crt,
        key=key,
        ta=ta,
        dns1=dns1,
        dns2=dns2,
        socks_line="",
        route_line="",
    )
    inner = {"config": ovpn, "clientId": client_id}
    url = protocols_document_to_vpn_url(
        container="amnezia-openvpn",
        protocol_last_config_objects={"openvpn": inner},
        host_name=host,
        dns1=dns1,
        dns2=dns2,
        description=_desc(s),
    )
    return _fname(VpnProtocol.OPENVPN), url


def issue_openvpn_cloak_vpn_url(s: Settings) -> tuple[str, str]:
    ctr = (s.docker_openvpn_cloak_container or "amnezia-openvpn-cloak").strip()
    host = _public_host(s)
    dns1, dns2 = _dns_pair(s)
    cloak_port_i = int(s.cloak_external_port)
    client_id = _rand_id(16)

    ck_raw = _dex_cat_bin(ctr, "/opt/amnezia/cloak/ck-config.json").decode()
    ck = json.loads(ck_raw)
    redir = str(ck.get("RedirAddr") or "tile.openstreetmap.org")

    cloak_pub = (
        _dex_cat_bin(ctr, "/opt/amnezia/cloak/cloak_public.key").decode().strip()
    )  # noqa: E501
    bypass_uid = (
        _dex_cat_bin(ctr, "/opt/amnezia/cloak/cloak_bypass_uid.key").decode().strip()
    )  # noqa: E501

    ss_raw = _dex_cat_bin(
        ctr, "/opt/amnezia/shadowsocks/ss-config.json"
    ).decode()  # noqa: E501
    ssj = json.loads(ss_raw)
    method = str(ssj.get("method") or "chacha20-ietf-poly1305")
    password = str(ssj.get("password") or "")
    if not password:
        password = (
            _dex_cat_bin(ctr, "/opt/amnezia/shadowsocks/shadowsocks.key")
            .decode()
            .strip()
        )  # noqa: E501

    with _flock(f"cloak_{ctr}"):
        ca, crt, key, ta = _easyrsa_issue(ctr, client_id)

    ovpn = _build_openvpn_ovpn(
        remote_host="127.0.0.1",
        remote_port=1194,
        proto="tcp",
        ca=ca,
        cert=crt,
        key=key,
        ta=ta,
        dns1=dns1,
        dns2=dns2,
        socks_line="",
        route_line=f"route {host} 255.255.255.255 net_gateway\n",
    )

    ss_inner = {
        "server": host,
        "server_port": cloak_port_i,
        "local_port": 8585,
        "password": password,
        "timeout": 60,
        "method": method,
    }
    cloak_inner = {
        "Transport": "direct",
        "ProxyMethod": "openvpn",
        "EncryptionMethod": "aes-gcm",
        "UID": bypass_uid,
        "PublicKey": cloak_pub,
        "ServerName": redir,
        "NumConn": 1,
        "BrowserSig": "chrome",
        "StreamTimeout": 300,
        "RemoteHost": host,
        "RemotePort": cloak_port_i,
    }
    blocks = {
        "openvpn": {"config": ovpn, "clientId": client_id},
        "shadowsocks": ss_inner,
        "cloak": cloak_inner,
    }
    url = protocols_document_to_vpn_url(
        container="amnezia-openvpn-cloak",
        protocol_last_config_objects=blocks,
        host_name=host,
        dns1=dns1,
        dns2=dns2,
        description=_desc(s),
    )
    return _fname(VpnProtocol.OPENVPN_CLOAK), url


def issue_openvpn_ss_vpn_url(s: Settings) -> tuple[str, str]:
    ctr = (s.docker_shadowsocks_container or "amnezia-shadowsocks").strip()
    host = _public_host(s)
    dns1, dns2 = _dns_pair(s)
    ss_port = int(s.shadowsocks_public_port)
    client_id = _rand_id(16)

    ss_raw = _dex_cat_bin(
        ctr, "/opt/amnezia/shadowsocks/ss-config.json"
    ).decode()  # noqa: E501
    ssj = json.loads(ss_raw)
    method = str(ssj.get("method") or "chacha20-ietf-poly1305")
    password = str(ssj.get("password") or "")
    if not password:
        password = (
            _dex_cat_bin(ctr, "/opt/amnezia/shadowsocks/shadowsocks.key")
            .decode()
            .strip()
        )  # noqa: E501

    with _flock(f"ovpnss_{ctr}"):
        ca, crt, key, ta = _easyrsa_issue(ctr, client_id)

    ovpn = _build_openvpn_ovpn(
        remote_host=host,
        remote_port=1194,
        proto="tcp",
        ca=ca,
        cert=crt,
        key=key,
        ta=ta,
        dns1=dns1,
        dns2=dns2,
        socks_line="socks-proxy 127.0.0.1 8585\n",
        route_line=f"route {host} 255.255.255.255 net_gateway\n",
    )
    ss_inner = {
        "server": host,
        "server_port": ss_port,
        "local_port": 8585,
        "password": password,
        "timeout": 60,
        "method": method,
    }
    url = protocols_document_to_vpn_url(
        container="amnezia-shadowsocks",
        protocol_last_config_objects={
            "openvpn": {"config": ovpn, "clientId": client_id},
            "shadowsocks": ss_inner,
        },
        host_name=host,
        dns1=dns1,
        dns2=dns2,
        description=_desc(s),
    )
    return _fname(VpnProtocol.OPENVPN_SS), url


def issue_ipsec_vpn_url(s: Settings) -> tuple[str, str]:
    ctr = (s.docker_ipsec_container or "amnezia-ipsec").strip()
    host = _public_host(s)
    dns1, dns2 = _dns_pair(s)
    client_id = _rand_id(16)
    p12_path = f"/opt/amnezia/ikev2/clients/{client_id}.p12"

    with _flock(f"ipsec_{ctr}"):
        _dex_sh(
            ctr,
            f'bash -c "certutil -z <(head -c 1024 /dev/urandom) '
            f"-S -c 'IKEv2 VPN CA' -n '{client_id}' "
            f"-s 'O=IKEv2 VPN,CN={client_id}' "
            f"-k rsa -g 3072 -v 120 -d sql:/etc/ipsec.d -t ',,' "
            f"--keyUsage digitalSignature,keyEncipherment "
            f"--extKeyUsage serverAuth,clientAuth -8 '{client_id}'\"",
            timeout=300,
        )
        _dex_sh(
            ctr,
            f'pk12util -W "" -d sql:/etc/ipsec.d -n "{client_id}" -o "{p12_path}"',  # noqa: E501
            timeout=120,
        )
        p12 = _dex_cat_bin(ctr, p12_path)

    inner = {
        "hostName": host,
        "userName": client_id,
        "cert": base64.b64encode(p12).decode("ascii"),
        "password": "",
    }
    url = protocols_document_to_vpn_url(
        container="amnezia-ipsec",
        protocol_last_config_objects={"ikev2": inner},
        host_name=host,
        dns1=dns1,
        dns2=dns2,
        description=_desc(s),
    )
    return _fname(VpnProtocol.IPSEC), url


def _provision_xray_client(s: Settings) -> tuple[dict, str, str]:
    """Новый UUID на сервере + vpn://. Возвращает xray_inner (клиентский JSON), vpn_url, filename."""  # noqa: E501
    ctr = (s.docker_xray_container or "amnezia-xray").strip()
    host = _public_host(s)
    dns1, dns2 = _dns_pair(s)
    path = "/opt/amnezia/xray/server.json"

    new_id = str(uuid.uuid4())
    client_cfg = {"flow": "xtls-rprx-vision", "id": new_id}

    with _flock(f"xray_{ctr}"):
        raw = _dex_cat_bin(ctr, path)
        doc = json.loads(raw.decode("utf-8"))
        inbound = None
        for ib in doc.get("inbounds") or []:
            if ib.get("protocol") == "vless":
                inbound = ib
                break
        if inbound is None:
            raise ContainerIssueError("В server.json нет VLESS inbound")
        settings = inbound.setdefault("settings", {})
        clients = settings.setdefault("clients", [])
        if not isinstance(clients, list):
            raise ContainerIssueError("settings.clients не массив")
        clients.append(client_cfg)
        settings["clients"] = clients
        new_json = json.dumps(doc, ensure_ascii=False, indent=4) + "\n"
        _write_container_path(ctr, path, new_json.encode("utf-8"))
        inbound_port = int(inbound.get("port") or 443)
        _apply_xray_config_with_safe_reload(
            ctr,
            path,
            inbound_port,
            allow_fallback_restart=bool(s.xray_restart_container),
        )
        pub = (
            _dex_cat_bin(ctr, "/opt/amnezia/xray/xray_public.key").decode().strip()
        )  # noqa: E501
        short_id = (
            _dex_cat_bin(ctr, "/opt/amnezia/xray/xray_short_id.key").decode().strip()
        )  # noqa: E501
        raw2 = _dex_cat_bin(ctr, path)
        doc2 = json.loads(raw2.decode("utf-8"))
        ib0 = next(
            (
                x for x in (doc2.get("inbounds") or []) if x.get("protocol") == "vless"
            ),  # noqa: E501
            None,
        )
        if not ib0:
            raise ContainerIssueError(
                "Xray: inbound потерян после перезапуска"
            )  # noqa: E501
        rs = (ib0.get("streamSettings") or {}).get("realitySettings") or {}
        snames = rs.get("serverNames") or []
        site = str(snames[0]) if snames else "www.microsoft.com"
        port = int(ib0.get("port") or 443)

    xray_inner = {
        "log": {"loglevel": "error"},
        "inbounds": [
            {
                "listen": "127.0.0.1",
                "port": 10808,
                "protocol": "socks",
                "settings": {"udp": True},
            }
        ],
        "outbounds": [
            {
                "protocol": "vless",
                "settings": {
                    "vnext": [
                        {
                            "address": host,
                            "port": port,
                            "users": [
                                {
                                    "id": new_id,
                                    "flow": "xtls-rprx-vision",
                                    "encryption": "none",
                                }
                            ],
                        }
                    ]
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "fingerprint": "chrome",
                        "serverName": site,
                        "publicKey": pub,
                        "shortId": short_id,
                        "spiderX": "",
                    },
                },
            }
        ],
    }
    url = protocols_document_to_vpn_url(
        container="amnezia-xray",
        protocol_last_config_objects={"xray": xray_inner},
        host_name=host,
        dns1=dns1,
        dns2=dns2,
        description=_desc(s),
    )
    filename = _fname(VpnProtocol.XRAY)
    return xray_inner, url, filename


def issue_xray_vpn_url(s: Settings) -> tuple[str, str]:
    _inner, url, filename = _provision_xray_client(s)
    return filename, url


def issue_xray_client_json_text(s: Settings) -> str:
    """Тот же новый клиент, что и для vpn://, но JSON для Xray-клиентов (без обёртки vpn://)."""  # noqa: E501
    xray_inner, _url, _fn = _provision_xray_client(s)
    return json.dumps(xray_inner, ensure_ascii=False, indent=2) + "\n"


def provision_wireguard_admin_key(
    s: Settings,
) -> tuple[str, "GeneratedVpnConfig"]:  # noqa: E501, F821
    """Один вызов provision: сырой wg.conf + объект для записи VpnKey (vpn:// в key_value)."""  # noqa: E501
    from vpn_bot.services.protocol_generators import GeneratedVpnConfig

    client_conf, pub, vpn_url, filename = _provision_plain_wireguard_client(s)
    cfg = GeneratedVpnConfig(
        filename=filename,
        key_value=vpn_url,
        wg_peer_public_key=pub,
    )
    return client_conf, cfg


def provision_xray_admin_key(
    s: Settings,
) -> tuple[str, "GeneratedVpnConfig"]:  # noqa: F821, E501
    """Один вызов provision: JSON клиента + объект для записи VpnKey."""
    from vpn_bot.services.protocol_generators import GeneratedVpnConfig

    inner, vpn_url, filename = _provision_xray_client(s)
    cfg = GeneratedVpnConfig(
        filename=filename,
        key_value=vpn_url,
        wg_peer_public_key=None,
    )
    raw_json = json.dumps(inner, ensure_ascii=False, indent=2) + "\n"
    return raw_json, cfg


def issue_amnezia_wg_vpn_url(
    s: Settings, conf_text: str, client_pub: str
) -> str:  # noqa: E501
    host = _public_host(s)
    dns1, dns2 = _dns_pair(s)
    mtu = (s.awg_client_mtu or "1376").strip() or "1376"
    return amnezia_awg_conf_to_vpn_url(
        conf_text,
        client_pub,
        host_name=host,
        dns1=dns1,
        dns2=dns2,
        description=_desc(s),
        mtu=mtu,
    )
