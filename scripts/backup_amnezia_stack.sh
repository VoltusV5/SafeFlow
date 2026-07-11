#!/usr/bin/env bash
# Снимок состояния Amnezia Docker (inspect + ключевые файлы из контейнеров).
# Не останавливает и не обновляет контейнеры. Запуск: bash scripts/backup_amnezia_stack.sh
# Остальные протоколы (xray, openvpn-cloak, …) не трогает — только перечисленные имена.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_ROOT:-/root/backups}/amnezia-stack-${STAMP}"
mkdir -p "$OUT"

CONTAINERS=(
  amnezia-awg
  amnezia-awg-20
  amnezia-wireguard
  amnezia-openvpn
  amnezia-openvpn-cloak
  amnezia-shadowsocks
  amnezia-ipsec
  amnezia-xray
)

for c in "${CONTAINERS[@]}"; do
  if docker inspect "$c" &>/dev/null; then
    docker inspect "$c" >"$OUT/${c}.inspect.json"
  else
    echo "{\"missing\":true,\"name\":\"$c\"}" >"$OUT/${c}.inspect.json"
  fi
done

# AWG: архив /opt/amnezia/awg из контейнеров (если есть)
for c in amnezia-awg amnezia-awg-20; do
  if docker exec "$c" test -d /opt/amnezia/awg 2>/dev/null; then
    docker exec "$c" tar czf - -C /opt/amnezia awg 2>/dev/null >"$OUT/${c}-opt-amnezia-awg.tgz" || true
  fi
done

# Xray
if docker exec amnezia-xray test -f /opt/amnezia/xray/server.json 2>/dev/null; then
  docker exec amnezia-xray cat /opt/amnezia/xray/server.json >"$OUT/amnezia-xray-server.json" 2>/dev/null || true
fi

# OpenVPN (без приватных ключей pki целиком — только client template если есть)
for c in amnezia-openvpn amnezia-openvpn-cloak; do
  if docker exec "$c" test -d /opt/amnezia/openvpn 2>/dev/null; then
    docker exec "$c" tar czf - -C /opt/amnezia openvpn 2>/dev/null >"$OUT/${c}-opt-amnezia-openvpn.tgz" || true
  fi
done

echo "OK: $OUT"
ls -la "$OUT" | head -40
