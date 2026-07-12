#!/usr/bin/env python3
"""Одноразово: копирует traffic_log, host_metric_samples, daily_stats из основной SQLite в analytics."""  # noqa: E501

from __future__ import annotations

import argparse
import asyncio
import os
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from vpn_bot.config import get_settings  # noqa: E402
from vpn_bot.db.session_analytics import init_analytics_db  # noqa: E402
from vpn_bot.utils.sqlite_backup import resolve_sqlite_path  # noqa: E402

TABLES = ("traffic_log", "host_metric_samples", "daily_stats")


async def _ensure_analytics_schema() -> None:
    await init_analytics_db()


def _migrate_rows(main_path: Path, ana_path: Path) -> None:
    ana_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ana_path), timeout=60.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute(f"ATTACH DATABASE ? AS m", (str(main_path),))  # noqa: F541, E501
        for t in TABLES:
            cur = conn.execute(
                "SELECT 1 FROM m.sqlite_master WHERE type='table' AND name=?",
                (t,),
            )
            if not cur.fetchone():
                print(f"[skip] {t}: нет в основной БД")
                continue
            n_src = conn.execute(f"SELECT COUNT(*) FROM m.{t}").fetchone()[0]
            if n_src == 0:
                print(f"[skip] {t}: 0 строк в основной")
                continue
            n_dest = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            if n_dest > 0:
                print(
                    f"[skip] {t}: в analytics уже {n_dest} строк "
                    "(очистите таблицу или удалите файл analytics для повтора)"
                )
                continue
            conn.execute(f"INSERT INTO {t} SELECT * FROM m.{t}")
            conn.commit()
            print(f"[ok] {t}: скопировано {n_src} строк")
        conn.execute("DETACH DATABASE m")
    finally:
        conn.close()


def _drop_main_tables(main_path: Path) -> None:
    conn = sqlite3.connect(str(main_path), timeout=60.0)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        for t in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        conn.commit()
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Перенос тяжёлых таблиц в отдельный файл analytics (см. ANALYTICS_DATABASE_URL).",  # noqa: E501
    )
    parser.add_argument(
        "--drop-main-tables",
        action="store_true",
        help="После копирования удалить эти таблицы в основной БД (сделайте бэкап!)",  # noqa: E501
    )
    args = parser.parse_args()
    os.chdir(_PROJECT_ROOT)
    s = get_settings()
    main_p = resolve_sqlite_path(s.database_url)
    ana_p = resolve_sqlite_path(s.analytics_database_url)
    if not main_p or not main_p.is_file():
        print("Основная SQLite не найдена (DATABASE_URL).", file=sys.stderr)
        sys.exit(1)
    if not ana_p:
        print("ANALYTICS_DATABASE_URL не указывает на SQLite.", file=sys.stderr)  # noqa: E501
        sys.exit(2)
    asyncio.run(_ensure_analytics_schema())
    _migrate_rows(main_p, ana_p)
    if args.drop_main_tables:
        _drop_main_tables(main_p)
        print("Таблицы удалены из основной БД.")


if __name__ == "__main__":
    main()
