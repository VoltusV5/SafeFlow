from __future__ import annotations

from vpn_bot.enums import VpnProtocol

_PLACEHOLDER_VPN_URI = (
    "vpn://AAAHLXjanVXdbpswFL7PU0RcBwSEpqGXnVRt6tSbTF2rEkUGThIrxEa2ya-Q9ip7hUp7j-yNZgP5gRASzUjIPt93Ph_bx8fbVls2LaBEIEyAce2h_ZHZVNseemWWJGloTmCDkb5iaK11ysTM9lBxz5AIcTGSOmM8USJbjyizp0V04imPfHywRbCASAGeBoxR5mk5Ie3sHTHxaUJCrkgfR-8ToUIMcwEkl7Lse8OUn-VpnSovpkwolmX2zf45yqigAS1C4jSY8RoNDkJgMuGVFR0JSRgrTLAEynB6HBbd4WGlNBG3LbUc5CIC_l9BLgisRGWu07atN-fOKAxZNm-2327XsGzHcCzDuu-fxVJ_AI7jNPISLrO1IbwbwjyK4TCPNLR803ctVwe_19OdMPB1hHqO7qNxz7QdsJy-3xj_UXIc0WUuuhIR11nMVvoCc0zJjQJAAraOReagZAglsM__Sy29DA_roRqPCjM9Tx3BAM0H1xKIgFhSNsujF0Fcu26ViEHCsFjnPKkcZYNaboFembo4AMkAue2YiFw6mDI6h4u7ryJhC2AvSJGUw3K5NCZUVSGBJnNEkNQzAjpvkIgTP8LBMxSr6Tqjqd59XQ8QeUL4zn3bvL48rtyfj8_2D_hKN-b7-3c-sMzkadYU11TeiW9Fit6HdtizAnB8F7p3vX6TX4xDYG-5X13qpFerj0dkr1Les0Kurqmq4PKa1sGCIcIVZ5RVI8WUGaCViGmr3BvmOloIY5RE4suV10byeMBwdkMUZfd79-fvr92n-rftA4lwS6Gy9KjvxGzn5uwh2JunlAt1_hlUqlpaK239A6Rjs9U"  # noqa: E501
)

_FILE_STEM: dict[VpnProtocol, str] = {
    VpnProtocol.AMNEZIA_WG: "amnezia_wg",
    VpnProtocol.WIREGUARD: "wireguard",
    VpnProtocol.OPENVPN: "open_vpn",
    VpnProtocol.OPENVPN_CLOAK: "open_vpn_clock",
    VpnProtocol.OPENVPN_SS: "open_vpn_ss",
    VpnProtocol.IPSEC: "ipsec",
    VpnProtocol.XRAY: "xray",
    VpnProtocol.XRAY_VLESS: "xray_vless",
    VpnProtocol.XRAY_TROJAN: "xray_trojan",
    VpnProtocol.XRAY_VMESS: "xray_vmess",
    VpnProtocol.XRAY_SHADOWSOCKS: "xray_shadowsocks",
}


def build_key_config(protocol: VpnProtocol, user_hint: str) -> tuple[str, str]:
    label = VpnProtocol.base_label(protocol)
    safe_hint = (user_hint or "").replace("\n", " ").strip()[:200]
    content = (
        f"# Заглушка: {label}. Пользователь: {safe_hint or '—'}\n"
        f"# Реальную генерацию подключите в vpn_bot.services.protocol_generators.\n"  # noqa: E501
        f"{_PLACEHOLDER_VPN_URI}"
    )
    filename = f"{_FILE_STEM[protocol]}.txt"
    return filename, content
