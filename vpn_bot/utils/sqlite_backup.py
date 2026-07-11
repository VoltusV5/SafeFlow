"""Снимок SQLite в отдельный файл через API backup (безопасно при работающем боте)."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy.engine.url import make_url


def resolve_sqlite_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        return None
    db = (url.database or "").strip()
    if not db:
        return None
    p = Path(db)
    if not p.is_absolute():
        p = Path(os.getcwd()) / p
    return p.resolve()


def sqlite_backup_to_tempfile(src_path: Path) -> Path:
    """Пишет согласованную копию в tempfile; вызывающий удаляет после отправки."""
    fd, name = tempfile.mkstemp(prefix="vpn_bot_db_", suffix=".sqlite3")
    os.close(fd)
    dst = Path(name)
    src_conn = sqlite3.connect(str(src_path), timeout=30.0)
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()
    return dst
