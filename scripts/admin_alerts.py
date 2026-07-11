#!/usr/bin/env python3
"""Алерты админу: свободное место на /, рост ошибок journalctl -p err по выбранным юнитам.

Падение systemd/Docker/SQLite покрывает scripts/vpn_bot_healthcheck.py (+ timer).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from vpn_bot.config import get_settings
from vpn_bot.utils.admin_notify import send_message_to_admins

_STATE_FILE = _PROJECT_ROOT / ".admin_alerts_state.json"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _load_state() -> dict:
    try:
        raw = _STATE_FILE.read_text(encoding="utf-8")
        return json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_FILE.write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(f"admin_alerts: cannot write state: {e}", file=sys.stderr)


def _cooldown_ok(state: dict, key: str, cooldown_min: int) -> bool:
    alerts = state.setdefault("alerts", {})
    raw = alerts.get(key)
    if not raw:
        return True
    try:
        last = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
    except ValueError:
        return True
    return _utc_now() - last >= timedelta(minutes=cooldown_min)


def _mark_sent(state: dict, key: str) -> None:
    state.setdefault("alerts", {})[key] = _utc_now().isoformat()


def _disk_free_pct(path: str = "/") -> float:
    du = shutil.disk_usage(path)
    return 100.0 * float(du.free) / float(du.total)


def _journal_err_count(units: list[str], window_min: int) -> int:
    if not units:
        return 0
    since = f"{int(window_min)} min ago"
    cmd = ["journalctl", "-q", "--no-pager", "-p", "err", "--since", since]
    for u in units:
        cmd.extend(["-u", u])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print(
            f"admin_alerts: journalctl failed: {(r.stderr or r.stdout)[:400]}",
            file=sys.stderr,
        )
        return -1
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    return len(lines)


def main() -> int:
    os.chdir(_PROJECT_ROOT)
    s = get_settings()
    if not s.admin_alerts_enabled:
        print("admin_alerts: disabled (ADMIN_ALERTS_ENABLED=false)")
        return 0
    if not s.admin_ids:
        print("admin_alerts: ADMIN_IDS empty, skip", file=sys.stderr)
        return 0

    state = _load_state()
    cooldown = max(1, int(s.admin_alert_cooldown_min))
    messages: list[str] = []

    # --- disk ---
    try:
        free_pct = _disk_free_pct("/")
    except OSError as e:
        messages.append(f"⚠️ Диск: не удалось измерить: {e}")
        free_pct = 100.0

    crit = int(s.admin_alert_disk_crit_pct)
    warn = int(s.admin_alert_disk_warn_pct)
    if free_pct <= float(crit):
        if _cooldown_ok(state, "disk_crit", cooldown):
            messages.append(
                f"🚨 Критично: на диске / свободно ~{free_pct:.1f}% "
                f"(порог {crit}%). Проверьте место и логи."
            )
            _mark_sent(state, "disk_crit")
    elif free_pct <= float(warn):
        if _cooldown_ok(state, "disk_warn", max(cooldown, 720)):
            messages.append(
                f"⚠️ Мало места на /: свободно ~{free_pct:.1f}% "
                f"(порог предупреждения {warn}%)."
            )
            _mark_sent(state, "disk_warn")

    # --- journal ---
    units = s.admin_journal_unit_list
    window = max(5, int(s.admin_alert_journal_window_min))
    if not units:
        print(
            "admin_alerts: ADMIN_JOURNAL_UNITS пуст — пропуск подсчёта journalctl.",
            file=sys.stderr,
        )
        n = -1
    else:
        n = _journal_err_count(units, window)
    prev_raw = state.get("journal_err_count")
    prev = prev_raw if isinstance(prev_raw, int) and prev_raw >= 0 else None

    abs_thr = max(1, int(s.admin_alert_journal_abs))
    ratio = float(s.admin_alert_journal_growth_ratio)
    floor = max(1, int(s.admin_alert_journal_growth_floor))

    spike = False
    if n >= 0 and prev is not None and prev > 0:
        spike = n >= prev * ratio and n >= floor

    fire = False
    if n >= 0:
        if n >= abs_thr:
            fire = True
        elif spike:
            fire = True

    if fire and n >= 0:
        if _cooldown_ok(state, "journal", cooldown):
            parts = [
                f"📋 journalctl -p err за последние {window} мин.",
                f"Юниты: {', '.join(units) if units else '(нет — задайте ADMIN_JOURNAL_UNITS)'}",
                f"Строк: {n}"
                + (f" (прошлый замер: {prev})" if prev is not None else " (первый замер)"),
            ]
            if n >= abs_thr:
                parts.append(f"Сработал порог «много ошибок»: ≥{abs_thr}.")
            if spike:
                parts.append(
                    f"Сработал рост: ≥{ratio:.1f}× от прошлого и ≥{floor} строк."
                )
            messages.append("\n".join(parts))
            _mark_sent(state, "journal")

    if n >= 0:
        state["journal_err_count"] = n
        state["journal_err_checked_at"] = _utc_now().isoformat()

    _save_state(state)

    if messages:
        send_message_to_admins("\n\n".join(messages))
        print("admin_alerts: sent", len(messages), "notification(s)")
        return 0

    print("admin_alerts: OK (no alerts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
