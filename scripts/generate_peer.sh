#!/usr/bin/env bash
# AmneziaWG peer: либо docker (контейнер Amnezia, wg0), либо хост (awg/wg на AWG_IFACE).
# Существующие peer в wg0.conf не удаляются — добавляется блок [Peer] и wg syncconf.
# Окружение: AWG_DOCKER_CONTAINER (напр. amnezia-awg), AWG_WG_IFACE (wg0), WG_ENDPOINT;
# WG_CLIENT_IP_PREFIX (10.8.1), WG_CLIENT_DNS; WG_SERVER_PUBLIC_KEY (можно пусто — возьмём из wg show).
# SKIP_WG_SET=1 — только JSON с конфигом клиента без изменений на сервере.

set -euo pipefail

HINT="${1:-bot}"

emit_json() {
  python3 <<'PY'
import json, os
conf = os.environ["_CLIENT_CONF"]
print(
    json.dumps(
        {
            "ok": True,
            "public_key": os.environ["_PUB"],
            "conf": conf,
            "vpn_url": "",
            "filename": "amnezia_wg.conf",
        },
        ensure_ascii=False,
    )
)
PY
}

build_client_conf() {
  # env: _PRIV _PUB _ADDR _DNS _SPUB _ENDP plus Jc Jmin Jmax S1 S2 H1-H4 _PSK
  export _CLIENT_CONF
  _CLIENT_CONF="$(python3 <<'PY'
import os
lines = [
    "[Interface]",
    f"# hint: {os.environ.get('_HINT', '')}",
    f"PrivateKey = {os.environ['_PRIV']}",
    f"Address = {os.environ['_ADDR']}",
    f"DNS = {os.environ['_DNS']}",
]
for k in (
    "Jc", "Jmin", "Jmax", "S1", "S2", "S3", "S4", "H1", "H2", "H3", "H4",
    "I1", "I2", "I3", "I4", "I5",
):
    v = os.environ.get(k, "").strip()
    if v:
        lines.append(f"{k} = {v}")
lines.extend(
    [
        "",
        "[Peer]",
        f"PublicKey = {os.environ['_SPUB']}",
        f"PresharedKey = {os.environ['_PSK']}",
        f"Endpoint = {os.environ['_ENDP']}",
        "AllowedIPs = 0.0.0.0/0, ::/0",
        "PersistentKeepalive = 25",
    ]
)
print("\n".join(lines))
PY
)"
}

docker_amnezia_flow() {
  local CTR="${AWG_DOCKER_CONTAINER:?AWG_DOCKER_CONTAINER not set}"
  local IFACE="${AWG_WG_IFACE:-wg0}"
  local CONF="${AWG_WG_CONF:-/opt/amnezia/awg/wg0.conf}"
  local PREFIX="${WG_CLIENT_IP_PREFIX:-10.8.1}"
  local DNS="${WG_CLIENT_DNS:-1.1.1.1}"

  if ! command -v docker >/dev/null 2>&1; then
    echo '{"ok":false,"error":"docker not found on host"}'
    exit 1
  fi
  if [[ -z "${WG_ENDPOINT:-}" ]]; then
    echo '{"ok":false,"error":"WG_ENDPOINT must be set (host:port UDP)"}'
    exit 1
  fi

  local SPUB="${WG_SERVER_PUBLIC_KEY:-}"
  if [[ -z "$SPUB" ]]; then
    SPUB="$(docker exec "$CTR" wg show "$IFACE" 2>/dev/null | awk '/public key:/{print $3}')"
  fi
  if [[ -z "$SPUB" ]]; then
    # Некоторые состояния wg0 (wireguard-go) не печатают «public key:» в wg show — берём из файла Amnezia
    SPUB="$(docker exec "$CTR" sh -c "d=\$(dirname \"$CONF\"); f=\"\$d/wireguard_server_public_key.key\"; test -f \"\$f\" && tr -d '\r\n' <\"\$f\" || true")"
  fi
  if [[ -z "$SPUB" ]]; then
    echo '{"ok":false,"error":"WG_SERVER_PUBLIC_KEY empty and wg show failed"}'
    exit 1
  fi

  local PSK
  PSK="$(docker exec "$CTR" sh -c "grep -m1 '^PresharedKey' '$CONF' 2>/dev/null | sed 's/^PresharedKey = //' | tr -d '\r\n'")"
  if [[ -z "$PSK" ]]; then
    # Чистый wg0.conf только с [Interface] (новый стек AWG 2.0): PSK лежит рядом в wireguard_psk.key
    PSK="$(docker exec "$CTR" sh -c "d=\$(dirname \"$CONF\"); test -f \"\$d/wireguard_psk.key\" && tr -d '\r\n' <\"\$d/wireguard_psk.key\" || true")"
  fi
  if [[ -z "$PSK" ]]; then
    echo '{"ok":false,"error":"Could not read PresharedKey from server config or wireguard_psk.key"}'
    exit 1
  fi

  local JC JMIN JMAX S1 S2 S3 S4 H1 H2 H3 H4
  JC="$(docker exec "$CTR" sh -c "grep -m1 '^Jc' '$CONF' | sed 's/^Jc = //'")"
  JMIN="$(docker exec "$CTR" sh -c "grep -m1 '^Jmin' '$CONF' | sed 's/^Jmin = //'")"
  JMAX="$(docker exec "$CTR" sh -c "grep -m1 '^Jmax' '$CONF' | sed 's/^Jmax = //'")"
  S1="$(docker exec "$CTR" sh -c "grep -m1 '^S1' '$CONF' | sed 's/^S1 = //'")"
  S2="$(docker exec "$CTR" sh -c "grep -m1 '^S2' '$CONF' | sed 's/^S2 = //'")"
  # AmneziaWG 2.0: в [Interface] сервера могут быть S3/S4 (на legacy их нет — grep не падает из-за «; true»)
  S3="$(docker exec "$CTR" sh -c "grep -m1 -iE '^s3[[:space:]]*=' '$CONF' 2>/dev/null | sed -E 's/^s3[[:space:]]*=[[:space:]]*//i' | tr -d '\r'; true")"
  S4="$(docker exec "$CTR" sh -c "grep -m1 -iE '^s4[[:space:]]*=' '$CONF' 2>/dev/null | sed -E 's/^s4[[:space:]]*=[[:space:]]*//i' | tr -d '\r'; true")"
  H1="$(docker exec "$CTR" sh -c "grep -m1 '^H1' '$CONF' | sed 's/^H1 = //'")"
  H2="$(docker exec "$CTR" sh -c "grep -m1 '^H2' '$CONF' | sed 's/^H2 = //'")"
  H3="$(docker exec "$CTR" sh -c "grep -m1 '^H3' '$CONF' | sed 's/^H3 = //'")"
  H4="$(docker exec "$CTR" sh -c "grep -m1 '^H4' '$CONF' | sed 's/^H4 = //'")"
  local I1 I2 I3 I4 I5
  I1="$(docker exec "$CTR" sh -c "grep -m1 '^I1' '$CONF' | sed 's/^I1 = //'")"
  I2="$(docker exec "$CTR" sh -c "grep -m1 '^I2' '$CONF' | sed 's/^I2 = //'")"
  I3="$(docker exec "$CTR" sh -c "grep -m1 '^I3' '$CONF' | sed 's/^I3 = //'")"
  I4="$(docker exec "$CTR" sh -c "grep -m1 '^I4' '$CONF' | sed 's/^I4 = //'")"
  I5="$(docker exec "$CTR" sh -c "grep -m1 '^I5' '$CONF' | sed 's/^I5 = //'")"

  local CLIENT_PRIV CLIENT_PUB
  CLIENT_PRIV="$(docker exec "$CTR" wg genkey | tr -d '\r\n')"
  CLIENT_PUB="$(printf '%s\n' "$CLIENT_PRIV" | docker exec -i "$CTR" wg pubkey | tr -d '\r\n')"

  local USED OCT
  # Только полные AllowedIPs = x.x.x.N/32 — иначе 10.8.1.2 совпадёт с 10.8.1.20
  USED="$(
    docker exec "$CTR" sh -c \
      "grep -oE 'AllowedIPs = ${PREFIX//./\\.}\.[0-9]+/32' '$CONF' 2>/dev/null | sed -n 's/.*\\.\\([0-9]\\+\\)\\/32/\\1/p' | sort -n -u" \
      || true
  )"
  OCT=""
  for i in $(seq 2 254); do
    if echo "$USED" | grep -qx "$i"; then
      continue
    fi
    OCT=$i
    break
  done
  if [[ -z "$OCT" ]]; then
    echo '{"ok":false,"error":"No free IP in VPN subnet (2-254)"}'
    exit 1
  fi

  local ADDR="${PREFIX}.${OCT}/32"
  export _HINT="$HINT" _PRIV="$CLIENT_PRIV" _PUB="$CLIENT_PUB" _ADDR="$ADDR" _DNS="$DNS" \
    _SPUB="$SPUB" _ENDP="$WG_ENDPOINT" _PSK="$PSK" \
    Jc="$JC" Jmin="$JMIN" Jmax="$JMAX" S1="$S1" S2="$S2" S3="$S3" S4="$S4" H1="$H1" H2="$H2" H3="$H3" H4="$H4" \
    I1="$I1" I2="$I2" I3="$I3" I4="$I4" I5="$I5"
  build_client_conf

  if [[ "${SKIP_WG_SET:-0}" == "1" ]]; then
    emit_json
    exit 0
  fi

  local LOCK="/root/vpn-telegram-bot/.generate_peer.lock"
  touch "$LOCK" 2>/dev/null || LOCK="/tmp/vpn_bot_generate_peer.lock"
  exec 9>"$LOCK"
  if ! flock 9; then
    echo '{"ok":false,"error":"Could not acquire lock"}'
    exit 1
  fi

  if ! docker exec \
    -e PEER_PUB="$CLIENT_PUB" \
    -e PEER_OCT="$OCT" \
    -e PEER_PSK="$PSK" \
    -e PEER_PREFIX="$PREFIX" \
    -e AWG_CONF="$CONF" \
    -e AWG_IFACE="$IFACE" \
    "$CTR" sh -c '
set -eu
CONF="$AWG_CONF"
IFACE="$AWG_IFACE"
cp "$CONF" "${CONF}.bak.vpn_bot"
strip_sync() {
  wg-quick strip "$CONF" > "/tmp/wg.strip.vpn_bot"
  wg syncconf "$IFACE" "/tmp/wg.strip.vpn_bot"
  rm -f "/tmp/wg.strip.vpn_bot"
}
if ! {
  {
    echo ""
    echo "[Peer]"
    echo "PublicKey = ${PEER_PUB}"
    echo "PresharedKey = ${PEER_PSK}"
    echo "AllowedIPs = ${PEER_PREFIX}.${PEER_OCT}/32"
  } >> "$CONF"
  strip_sync
}; then
  cp "${CONF}.bak.vpn_bot" "$CONF"
  strip_sync || true
  exit 1
fi
'; then
    echo '{"ok":false,"error":"docker exec: append peer or syncconf failed; config rolled back in container"}'
    exit 1
  fi

  emit_json
}

host_awg_flow() {
  WG_CMD="$(command -v awg 2>/dev/null || command -v wg 2>/dev/null || true)"
  if [[ -z "${WG_CMD}" ]]; then
    echo '{"ok":false,"error":"awg/wg not found in PATH"}'
    exit 1
  fi

  IFACE="${AWG_IFACE:-awg0}"
  if [[ -z "${WG_SERVER_PUBLIC_KEY:-}" || -z "${WG_ENDPOINT:-}" ]]; then
    echo '{"ok":false,"error":"WG_SERVER_PUBLIC_KEY and WG_ENDPOINT must be set"}'
    exit 1
  fi

  CLIENT_PRIV="$("${WG_CMD}" genkey)"
  CLIENT_PUB="$(printf '%s\n' "${CLIENT_PRIV}" | "${WG_CMD}" pubkey)"

  OCT=$((2 + RANDOM % 250))
  ADDR="${WG_CLIENT_IP_PREFIX:-10.8.0}.${OCT}/32"
  DNS="${WG_CLIENT_DNS:-1.1.1.1}"

  if [[ "${SKIP_WG_SET:-0}" != "1" ]]; then
    if ! "${WG_CMD}" set "${IFACE}" peer "${CLIENT_PUB}" allowed-ips 0.0.0.0/0,::/0 2>/dev/null; then
      echo "{\"ok\":false,\"error\":\"wg set failed for iface ${IFACE}\"}"
      exit 1
    fi
  fi

  export _HINT="$HINT" _PRIV="$CLIENT_PRIV" _PUB="$CLIENT_PUB" _ADDR="$ADDR" _DNS="$DNS" \
    _SPUB="$WG_SERVER_PUBLIC_KEY" _ENDP="$WG_ENDPOINT" _PSK=""
  # host flow: без Amnezia junk — минимальный конфиг (может не подойти для AWG в приложении Amnezia)
  export Jc="" Jmin="" Jmax="" S1="" S2="" S3="" S4="" H1="" H2="" H3="" H4=""
  if [[ -z "${AMNEZIA_CLIENT_PSK:-}" ]]; then
    _CLIENT_CONF="$(python3 <<'PY'
import os
print(
    f"""[Interface]
# hint: {os.environ['_HINT']}
PrivateKey = {os.environ['_PRIV']}
Address = {os.environ['_ADDR']}
DNS = {os.environ['_DNS']}

[Peer]
PublicKey = {os.environ['_SPUB']}
Endpoint = {os.environ['_ENDP']}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""
)
PY
)"
  else
    export _PSK="$AMNEZIA_CLIENT_PSK"
    build_client_conf
  fi
  emit_json
}

if [[ -n "${AWG_DOCKER_CONTAINER:-}" ]]; then
  docker_amnezia_flow
else
  host_awg_flow
fi
