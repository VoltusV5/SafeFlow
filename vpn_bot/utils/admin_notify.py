"""Отправка сообщений администраторам через Telegram Bot API (тот же BOT_TOKEN)."""  # noqa: E501

from __future__ import annotations

import sys
import urllib.error
import urllib.parse
import urllib.request

from vpn_bot.config import get_settings


def send_message_to_admins(text: str) -> None:
    s = get_settings()
    if not s.admin_ids:
        print(
            "admin_notify: ADMIN_IDS пуст — уведомление не отправлено.",
            file=sys.stderr,
        )
        return
    token = s.bot_token
    body = (text or "")[:4000]
    for aid in s.admin_ids:
        try:
            data = urllib.parse.urlencode({"chat_id": str(aid), "text": body}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data=data,
                method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                resp.read()
        except (urllib.error.URLError, OSError) as e:
            print(f"admin_notify: Telegram {aid}: {e}", file=sys.stderr)
