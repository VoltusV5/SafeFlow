from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from vpn_bot.config import get_settings
from vpn_bot.enums import VpnProtocol
from vpn_bot.services.amnezia_protocols import (
    issue_amnezia_wg_vpn_url,
    issue_ipsec_vpn_url,
    issue_openvpn_cloak_vpn_url,
    issue_openvpn_ss_vpn_url,
    issue_openvpn_vpn_url,
    issue_wireguard_vpn_url,
    issue_xray_vpn_url,
)
from vpn_bot.services.clean_xray_service import (
    issue_clean_xray_ss_url,
    issue_clean_xray_trojan_url,
    issue_clean_xray_vless_url,
    issue_clean_xray_vmess_url,
)
from vpn_bot.services.keygen import _FILE_STEM, build_key_config
from vpn_bot.vpn_generator import generate_amnezia_wg_peer


@dataclass(frozen=True)
class GeneratedVpnConfig:
    filename: str
    key_value: str
    wg_peer_public_key: str | None = None


def _stub(protocol: VpnProtocol, hint: str) -> GeneratedVpnConfig:
    filename, key_value = build_key_config(protocol, hint)
    return GeneratedVpnConfig(
        filename=filename,
        key_value=key_value,
        wg_peer_public_key=None,
    )


async def generate_amnezia_wg(hint: str) -> GeneratedVpnConfig:
    s = get_settings()
    if s.generate_peer_script.strip():
        _, body, pub = await generate_amnezia_wg_peer(hint)
        vpn_url = await asyncio.to_thread(
            issue_amnezia_wg_vpn_url, s, body, pub
        )  # noqa: E501
        fn = f"{_FILE_STEM[VpnProtocol.AMNEZIA_WG]}.txt"
        return GeneratedVpnConfig(fn, vpn_url, pub)
    return _stub(VpnProtocol.AMNEZIA_WG, hint)


async def generate_wireguard(hint: str) -> GeneratedVpnConfig:
    s = get_settings()
    fn, url, pub = await asyncio.to_thread(issue_wireguard_vpn_url, s)
    return GeneratedVpnConfig(fn, url, pub)


async def generate_openvpn(hint: str) -> GeneratedVpnConfig:
    s = get_settings()
    fn, url = await asyncio.to_thread(issue_openvpn_vpn_url, s)
    return GeneratedVpnConfig(fn, url, None)


async def generate_openvpn_cloak(hint: str) -> GeneratedVpnConfig:
    s = get_settings()
    fn, url = await asyncio.to_thread(issue_openvpn_cloak_vpn_url, s)
    return GeneratedVpnConfig(fn, url, None)


async def generate_openvpn_ss(hint: str) -> GeneratedVpnConfig:
    s = get_settings()
    fn, url = await asyncio.to_thread(issue_openvpn_ss_vpn_url, s)
    return GeneratedVpnConfig(fn, url, None)


async def generate_ipsec(hint: str) -> GeneratedVpnConfig:
    s = get_settings()
    fn, url = await asyncio.to_thread(issue_ipsec_vpn_url, s)
    return GeneratedVpnConfig(fn, url, None)


async def generate_xray(hint: str) -> GeneratedVpnConfig:
    s = get_settings()
    fn, url = await asyncio.to_thread(issue_xray_vpn_url, s)
    return GeneratedVpnConfig(fn, url, None)


async def generate_xray_vless(hint: str) -> GeneratedVpnConfig:
    fn, url = await asyncio.to_thread(issue_clean_xray_vless_url)
    return GeneratedVpnConfig(fn, url, None)


async def generate_xray_trojan(hint: str) -> GeneratedVpnConfig:
    fn, url = await asyncio.to_thread(issue_clean_xray_trojan_url)
    return GeneratedVpnConfig(fn, url, None)


async def generate_xray_vmess(hint: str) -> GeneratedVpnConfig:
    fn, url = await asyncio.to_thread(issue_clean_xray_vmess_url)
    return GeneratedVpnConfig(fn, url, None)


async def generate_xray_shadowsocks(hint: str) -> GeneratedVpnConfig:
    fn, url = await asyncio.to_thread(issue_clean_xray_ss_url)
    return GeneratedVpnConfig(fn, url, None)


_GeneratorFn = Callable[[str], Awaitable[GeneratedVpnConfig]]

_GENERATORS: dict[VpnProtocol, _GeneratorFn] = {
    VpnProtocol.AMNEZIA_WG: generate_amnezia_wg,
    VpnProtocol.WIREGUARD: generate_wireguard,
    VpnProtocol.OPENVPN: generate_openvpn,
    VpnProtocol.OPENVPN_CLOAK: generate_openvpn_cloak,
    VpnProtocol.OPENVPN_SS: generate_openvpn_ss,
    VpnProtocol.IPSEC: generate_ipsec,
    VpnProtocol.XRAY: generate_xray,
    VpnProtocol.XRAY_VLESS: generate_xray_vless,
    VpnProtocol.XRAY_TROJAN: generate_xray_trojan,
    VpnProtocol.XRAY_VMESS: generate_xray_vmess,
    VpnProtocol.XRAY_SHADOWSOCKS: generate_xray_shadowsocks,
}


async def generate_for_protocol(
    protocol: VpnProtocol, hint: str
) -> GeneratedVpnConfig:  # noqa: E501
    return await _GENERATORS[protocol](hint)
