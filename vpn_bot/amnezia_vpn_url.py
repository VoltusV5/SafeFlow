"""Ссылка vpn:// для импорта в клиент Amnezia (как в exportController.cpp: qCompress + Base64Url)."""

from __future__ import annotations

import base64
import json
import re
import struct
import zlib


def decode_vpn_url(url: str) -> dict[str, object]:
    if not url.startswith("vpn://"):
        return {}
    try:
        b64 = url[6:]
        b64 += "=" * ((4 - len(b64) % 4) % 4)
        packed = base64.urlsafe_b64decode(b64)
        if len(packed) < 4:
            return {}
        plain = zlib.decompress(packed[4:])
        return json.loads(plain)
    except Exception:
        return {}


def _parse_wg_conf_sections(conf: str) -> dict[tuple[str, str], str]:
    section = "none"
    out: dict[tuple[str, str], str] = {}
    for raw in conf.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[(section, k.strip())] = v.strip()
    return out


def _parse_endpoint(endpoint: str) -> tuple[str, int]:
    endpoint = endpoint.strip()
    if endpoint.startswith("["):
        m = re.match(r"^\[([0-9a-fA-F:.]+)\]:(\d+)$", endpoint)
        if m:
            return m.group(1), int(m.group(2))
    if ":" in endpoint:
        host, _, port_s = endpoint.rpartition(":")
        return host.strip(), int(port_s.strip())
    return endpoint, 51820


def build_awg_last_config_object(
    conf_text: str,
    client_pub_key: str,
    *,
    mtu: str = "1376",
) -> dict[str, object]:
    """Объект JSON для awg.last_config (до сериализации в строку)."""
    m = _parse_wg_conf_sections(conf_text)
    priv = m.get(("interface", "PrivateKey"), "")
    addr = m.get(("interface", "Address"), "")
    client_ip = addr.split("/")[0].strip() if addr else ""
    server_pub = m.get(("peer", "PublicKey"), "")
    psk = m.get(("peer", "PresharedKey"), "")
    endpoint = m.get(("peer", "Endpoint"), "")
    host, port = _parse_endpoint(endpoint) if endpoint else ("", 0)

    junk_keys = (
        ("Jc", ("interface", "Jc")),
        ("Jmin", ("interface", "Jmin")),
        ("Jmax", ("interface", "Jmax")),
        ("S1", ("interface", "S1")),
        ("S2", ("interface", "S2")),
        ("S3", ("interface", "S3")),
        ("S4", ("interface", "S4")),
        ("H1", ("interface", "H1")),
        ("H2", ("interface", "H2")),
        ("H3", ("interface", "H3")),
        ("H4", ("interface", "H4")),
        ("I1", ("interface", "I1")),
        ("I2", ("interface", "I2")),
        ("I3", ("interface", "I3")),
        ("I4", ("interface", "I4")),
        ("I5", ("interface", "I5")),
    )
    extra: dict[str, str] = {}
    for out_k, mkey in junk_keys:
        v = m.get(mkey, "")
        if not v and len(mkey) == 2 and mkey[0] == "interface":
            v = m.get((mkey[0], mkey[1].lower()), "")
        if v:
            extra[out_k] = v

    inner: dict[str, object] = {
        "config": conf_text,
        "hostName": host,
        "port": port,
        "client_priv_key": priv,
        "client_pub_key": client_pub_key,
        "client_ip": client_ip,
        "psk_key": psk,
        "server_pub_key": server_pub,
        "mtu": mtu,
        "persistent_keep_alive": "25",
        "allowed_ips": ["0.0.0.0/0", "::/0"],
        "clientId": client_pub_key,
    }
    inner.update(extra)
    return inner


def build_amnezia_awg_share_document(
    conf_text: str,
    client_pub_key: str,
    *,
    host_name: str,
    dns1: str,
    dns2: str,
    description: str,
    mtu: str = "1376",
) -> dict[str, object]:
    """Корневой JSON как у экспорта Amnezia (один контейнер amnezia-awg)."""
    inner = build_awg_last_config_object(
        conf_text, client_pub_key, mtu=mtu
    )
    last_cfg = json.dumps(inner, ensure_ascii=False, indent=4)
    return {
        "containers": [
            {
                "container": "amnezia-awg",
                "awg": {
                    "last_config": last_cfg,
                },
            }
        ],
        "defaultContainer": "amnezia-awg",
        "description": description,
        "dns1": dns1,
        "dns2": dns2,
        "hostName": host_name,
    }


def encode_vpn_url(document: dict[str, object]) -> str:
    """Qt qCompress (уровень 8) + 4 байта размера + Base64Url без padding."""
    text = json.dumps(document, ensure_ascii=False, indent=4)
    plain = text.encode("utf-8")
    z = zlib.compress(plain, 8)
    packed = struct.pack(">I", len(plain)) + z
    b64 = base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")
    return f"vpn://{b64}"


def amnezia_awg_conf_to_vpn_url(
    conf_text: str,
    client_pub_key: str,
    *,
    host_name: str,
    dns1: str,
    dns2: str,
    description: str,
    mtu: str = "1376",
) -> str:
    doc = build_amnezia_awg_share_document(
        conf_text,
        client_pub_key,
        host_name=host_name,
        dns1=dns1,
        dns2=dns2,
        description=description,
        mtu=mtu,
    )
    return encode_vpn_url(doc)


def build_amnezia_share_document(
    *,
    container: str,
    protocol_last_config_objects: dict[str, dict[str, object]],
    host_name: str,
    dns1: str,
    dns2: str,
    description: str,
) -> dict[str, object]:
    """Один контейнер, несколько протоколов (openvpn-cloak: openvpn+shadowsocks+cloak)."""
    block: dict[str, object] = {"container": container}
    for proto_key, inner in protocol_last_config_objects.items():
        block[proto_key] = {
            "last_config": json.dumps(inner, ensure_ascii=False, indent=4),
        }
    return {
        "containers": [block],
        "defaultContainer": container,
        "description": description,
        "dns1": dns1,
        "dns2": dns2,
        "hostName": host_name,
    }


def protocols_document_to_vpn_url(
    *,
    container: str,
    protocol_last_config_objects: dict[str, dict[str, object]],
    host_name: str,
    dns1: str,
    dns2: str,
    description: str,
) -> str:
    doc = build_amnezia_share_document(
        container=container,
        protocol_last_config_objects=protocol_last_config_objects,
        host_name=host_name,
        dns1=dns1,
        dns2=dns2,
        description=description,
    )
    return encode_vpn_url(doc)
