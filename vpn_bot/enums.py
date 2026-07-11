from enum import StrEnum


class VpnProtocol(StrEnum):
    AMNEZIA_WG = "amnezia_wg"
    WIREGUARD = "wireguard"
    OPENVPN = "openvpn"
    OPENVPN_CLOAK = "openvpn_cloak"
    OPENVPN_SS = "openvpn_ss"
    IPSEC = "ipsec"
    XRAY = "xray"
    XRAY_VLESS = "xray_vless"
    XRAY_TROJAN = "xray_trojan"
    XRAY_VMESS = "xray_vmess"
    XRAY_SHADOWSOCKS = "xray_shadowsocks"

    @classmethod
    def base_label(cls, value: "VpnProtocol") -> str:
        return _BASE_LABELS[value]

    @classmethod
    def label(cls, value: "VpnProtocol") -> str:
        s = _BASE_LABELS[value]
        if value in RECOMMENDED_PROTOCOLS:
            return f"{s} ⭐"
        return s


_BASE_LABELS: dict[VpnProtocol, str] = {
    VpnProtocol.AMNEZIA_WG: "Amnezia WG",
    VpnProtocol.WIREGUARD: "Wireguard",
    VpnProtocol.OPENVPN: "Open VPN",
    VpnProtocol.OPENVPN_CLOAK: "Open VPN over Clock",
    VpnProtocol.OPENVPN_SS: "Open VPN over SS",
    VpnProtocol.IPSEC: "IPsec",
    VpnProtocol.XRAY: "Xray WG",
    VpnProtocol.XRAY_VLESS: "Xray VLESS",
    VpnProtocol.XRAY_TROJAN: "Xray Trojan",
    VpnProtocol.XRAY_VMESS: "Xray VMess",
    VpnProtocol.XRAY_SHADOWSOCKS: "Xray Shadowsocks",
}

RECOMMENDED_PROTOCOLS: frozenset[VpnProtocol] = frozenset(
    {
        VpnProtocol.AMNEZIA_WG,
        VpnProtocol.OPENVPN_CLOAK,
        VpnProtocol.XRAY,
        VpnProtocol.XRAY_VLESS,
    }
)


class KeyDelivery(StrEnum):
    MESSAGE = "message"
    FILE = "file"
    QR = "qr"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
