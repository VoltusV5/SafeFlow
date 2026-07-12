import asyncio
import json
import logging
import subprocess

from vpn_bot.amnezia_vpn_url import decode_vpn_url
from vpn_bot.config import get_settings
from vpn_bot.db.models import VpnKey
from vpn_bot.enums import VpnProtocol

logger = logging.getLogger(__name__)

def _revoke_wg_peer(ctr: str, iface: str, conf: str, pubkey: str) -> None:  # noqa: E302, E501
    # Remove from runtime
    subprocess.run(["docker", "exec", ctr, "sh", "-c", f"wg set {iface} peer {pubkey} remove || true"], check=False, timeout=30)  # noqa: E501
      # noqa: W293, E114, E116
    # Remove from config file to survive restart
    try:
        raw = subprocess.check_output(["docker", "exec", ctr, "cat", conf], timeout=15)  # noqa: E501
        text = raw.decode("utf-8")
        blocks = text.split("\n[Peer]\n")
        new_blocks = [blocks[0]]
        for block in blocks[1:]:
            if f"PublicKey = {pubkey}" not in block:
                new_blocks.append(block)
        new_text = "\n[Peer]\n".join(new_blocks)
          # noqa: W293, E114, E116
        # Write back
        subprocess.run(["docker", "exec", "-i", ctr, "sh", "-c", f"cat > {conf}"], input=new_text.encode("utf-8"), check=False, timeout=15)  # noqa: E501
    except Exception as e:
        logger.warning(f"Failed to remove peer {pubkey} from {conf} in {ctr}: {e}")  # noqa: E501

def _revoke_xray(ctr: str, uuid: str) -> None:  # noqa: E302
    path = "/opt/amnezia/xray/server.json"
    cmd = f"""
cat {path} > /tmp/xray_server.json.bak
python3 -c '
import sys, json
path = "{path}"
with open(path, "r") as f:
    doc = json.load(f)
changed = False
for ib in doc.get("inbounds", []):
    if ib.get("protocol") == "vless":
        clients = ib.get("settings", {{}}).get("clients", [])
        new_clients = [c for c in clients if c.get("id") != "{uuid}"]
        if len(clients) != len(new_clients):
            ib["settings"]["clients"] = new_clients
            changed = True
if changed:
    with open(path, "w") as f:
        json.dump(doc, f, indent=4)
' && killall -HUP xray
"""
    subprocess.run(["docker", "exec", ctr, "sh", "-c", cmd], check=False, timeout=30)  # noqa: E501

def _revoke_openvpn(ctr: str, client_id: str) -> None:  # noqa: E302
    cmd = f"""
EASYRSA_PKI=/opt/amnezia/openvpn/pki /usr/share/easy-rsa/easyrsa --batch revoke {client_id} || true  # noqa: E501
EASYRSA_PKI=/opt/amnezia/openvpn/pki /usr/share/easy-rsa/easyrsa gen-crl || true  # noqa: E501
# restart openvpn to apply CRL
killall -HUP openvpn || true
"""
    subprocess.run(["docker", "exec", ctr, "sh", "-c", cmd], check=False, timeout=60)  # noqa: E501


def _revoke_ipsec(ctr: str, client_id: str) -> None:
    cmd = f"""
certutil -D -n "{client_id}" -d sql:/etc/ipsec.d || true
ipsec rereadall || true
"""
    subprocess.run(["docker", "exec", ctr, "sh", "-c", cmd], check=False, timeout=30)  # noqa: E501

async def revoke_key_on_server(key: VpnKey) -> None:  # noqa: C901, E302
    try:
        s = get_settings()
        if key.protocol == VpnProtocol.AMNEZIA_WG.value:
            pubkey = key.wg_peer_public_key
            if not pubkey: return  # noqa: E701
            ctr = (s.awg_docker_container or "").strip()
            if ctr:
                iface = (s.awg_wg_iface or "wg0").strip() or "wg0"
                conf = (s.awg_wg_conf or "/opt/amnezia/awg/wg0.conf").strip()
                await asyncio.to_thread(_revoke_wg_peer, ctr, iface, conf, pubkey)  # noqa: E501
            ctr2 = (s.awg2_docker_container or "").strip()
            if ctr2:
                iface2 = (s.awg2_wg_iface or "wg0").strip() or "wg0"
                conf2 = (s.awg2_wg_conf or "/opt/amnezia/awg/wg0.conf").strip()
                await asyncio.to_thread(_revoke_wg_peer, ctr2, iface2, conf2, pubkey)  # noqa: E501
            if not ctr and not ctr2:
                iface = (s.awg_iface or "awg0").strip()
                cmd = f"awg set {iface} peer {pubkey} remove || wg set {iface} peer {pubkey} remove || true"  # noqa: E501
                await asyncio.create_subprocess_shell(cmd)
        elif key.protocol == VpnProtocol.WIREGUARD.value:
            pubkey = key.wg_peer_public_key
            if not pubkey: return  # noqa: E701
            ctr = (s.docker_wireguard_container or "amnezia-wireguard").strip()
            if ctr:
                iface = "wg0"
                conf = (s.wireguard_wg_conf or "/opt/amnezia/wireguard/wg0.conf").strip()  # noqa: E501
                await asyncio.to_thread(_revoke_wg_peer, ctr, iface, conf, pubkey)  # noqa: E501
        elif key.protocol == VpnProtocol.XRAY.value:
            ctr = (s.docker_xray_container or "amnezia-xray").strip()
            if not ctr: return  # noqa: E701
            url = key.key_value.strip()
            doc = decode_vpn_url(url)
            if not doc: return  # noqa: E701
            cfg_str = doc.get("containers", [{}])[0].get("xray", {}).get("last_config", "")  # noqa: E501
            if not cfg_str: return  # noqa: E701
            cfg = json.loads(cfg_str)
            uuid = cfg["outbounds"][0]["settings"]["vnext"][0]["users"][0]["id"]  # noqa: E501
            if uuid:
                await asyncio.to_thread(_revoke_xray, ctr, uuid)
        elif key.protocol in (VpnProtocol.OPENVPN.value, VpnProtocol.OPENVPN_CLOAK.value, VpnProtocol.OPENVPN_SS.value):  # noqa: E501
            if key.protocol == VpnProtocol.OPENVPN.value:
                ctr = (s.docker_openvpn_container or "amnezia-openvpn").strip()
            elif key.protocol == VpnProtocol.OPENVPN_CLOAK.value:
                ctr = (s.docker_openvpn_cloak_container or "amnezia-openvpn-cloak").strip()  # noqa: E501
            else:
                ctr = (s.docker_shadowsocks_container or "amnezia-shadowsocks").strip()  # noqa: E501
            if not ctr: return  # noqa: E701
            url = key.key_value.strip()
            doc = decode_vpn_url(url)
            if not doc: return  # noqa: E701
            client_id = doc.get("containers", [{}])[0].get("openvpn", {}).get("clientId", "")  # noqa: E501
            if client_id:
                await asyncio.to_thread(_revoke_openvpn, ctr, client_id)
        elif key.protocol == VpnProtocol.IPSEC.value:
            ctr = (s.docker_ipsec_container or "amnezia-ipsec").strip()
            if not ctr: return  # noqa: E701
            url = key.key_value.strip()
            doc = decode_vpn_url(url)
            if not doc: return  # noqa: E701
            client_id = doc.get("containers", [{}])[0].get("ikev2", {}).get("userName", "")  # noqa: E501
            if client_id:
                await asyncio.to_thread(_revoke_ipsec, ctr, client_id)
    except Exception as e:
        logger.warning(f"Failed to revoke key {key.id} on server: {e}")
