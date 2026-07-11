#!/usr/bin/env bash
set -euo pipefail

SRC_DB="/root/vpn-telegram-bot/vpn_bot.db"
LOCAL_DIR="/root/backups/vpn-bot"
REMOTE_NAME="${REMOTE_NAME:-yandex}"
REMOTE_DIR="${REMOTE_DIR:-vpn-telegram-bot/backups}"
LOCAL_KEEP="${LOCAL_KEEP:-1}"
REMOTE_KEEP="${REMOTE_KEEP:-1}"

mkdir -p "$LOCAL_DIR"

if [[ ! -f "$SRC_DB" ]]; then
  echo "source sqlite db not found: $SRC_DB" >&2
  exit 1
fi

TS="$(date +%F_%H-%M)"
BASE="vpn_bot_${TS}"
OUT_DB="${LOCAL_DIR}/${BASE}.db"
OUT_GZ="${OUT_DB}.gz"
SHA_PATH="${OUT_GZ}.sha256"

# Consistent online backup via sqlite3 backup API
python3 - <<'PY' "$SRC_DB" "$OUT_DB"
import sqlite3
import sys
src, dst = sys.argv[1], sys.argv[2]
src_conn = sqlite3.connect(src)
dst_conn = sqlite3.connect(dst)
with dst_conn:
    src_conn.backup(dst_conn)
src_conn.close()
dst_conn.close()
PY

gzip -f "$OUT_DB"
sha256sum "$OUT_GZ" > "$SHA_PATH"

rclone copyto "$OUT_GZ" "${REMOTE_NAME}:${REMOTE_DIR}/${BASE}.db.gz"
rclone copyto "$SHA_PATH" "${REMOTE_NAME}:${REMOTE_DIR}/${BASE}.db.gz.sha256"

mapfile -t REMOTE_DBS < <(
  rclone lsf "${REMOTE_NAME}:${REMOTE_DIR}" --files-only \
    | grep -E '^vpn_bot_[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}\.db\.gz$' \
    | sort
)
if (( ${#REMOTE_DBS[@]} > REMOTE_KEEP )); then
  TO_DELETE=$(( ${#REMOTE_DBS[@]} - REMOTE_KEEP ))
  for ((i=0; i<TO_DELETE; i++)); do
    OLD="${REMOTE_DBS[$i]}"
    rclone deletefile "${REMOTE_NAME}:${REMOTE_DIR}/${OLD}" || true
    rclone deletefile "${REMOTE_NAME}:${REMOTE_DIR}/${OLD}.sha256" || true
  done
fi

mapfile -t LOCAL_DBS < <(
  ls -1 "${LOCAL_DIR}"/vpn_bot_*.db.gz 2>/dev/null | sort || true
)
if (( ${#LOCAL_DBS[@]} > LOCAL_KEEP )); then
  TO_DELETE_LOCAL=$(( ${#LOCAL_DBS[@]} - LOCAL_KEEP ))
  for ((i=0; i<TO_DELETE_LOCAL; i++)); do
    OLD_PATH="${LOCAL_DBS[$i]}"
    rm -f "$OLD_PATH" "${OLD_PATH}.sha256"
  done
fi

echo "backup ok: ${BASE}.db.gz"
