from __future__ import annotations

from pathlib import Path

from vpn_bot.config import get_settings

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent


def resolved_guides_src_dir() -> Path:
    raw = (get_settings().guides_src_dir or "Src").strip()
    p = Path(raw).expanduser()
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()
