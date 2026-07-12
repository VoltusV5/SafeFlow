from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vpn_bot.config import get_settings
from vpn_bot.db.base import Base

_settings = get_settings()

_engine_kw: dict = {"echo": False}
if "sqlite" in _settings.database_url.lower():
    # Дольше ждём lock при конкуренции бот + демоны (несколько процессов).
    _engine_kw["connect_args"] = {"timeout": 30.0}

engine = create_async_engine(_settings.database_url, **_engine_kw)


@event.listens_for(engine.sync_engine, "connect")
def _sqlite_on_connect(dbapi_conn, connection_record) -> None:
    if engine.dialect.name != "sqlite":
        return
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA busy_timeout=30000")
    finally:
        cur.close()


async_session_maker = async_sessionmaker(  # noqa: E305
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    from vpn_bot.db import models as _models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in _settings.database_url.lower():
            # WAL: читатели не блокируют писателя — критично при bot + 2 демона.  # noqa: E501
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            r = await conn.execute(text("PRAGMA table_info(users)"))
            cols = [row[1] for row in r.fetchall()]
            if cols and "password_fail_attempts" not in cols:
                await conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN password_fail_attempts "
                        "INTEGER NOT NULL DEFAULT 0"
                    )
                )
            r2 = await conn.execute(text("PRAGMA table_info(vpn_keys)"))
            kcols = [row[1] for row in r2.fetchall()]
            if kcols and "wg_peer_public_key" not in kcols:
                await conn.execute(
                    text(
                        "ALTER TABLE vpn_keys ADD COLUMN wg_peer_public_key "
                        "VARCHAR(64)"
                    )
                )
            r3 = await conn.execute(text("PRAGMA table_info(vpn_keys)"))
            kcols3 = [row[1] for row in r3.fetchall()]
            if kcols3 and "last_activity_at" not in kcols3:
                await conn.execute(
                    text(
                        "ALTER TABLE vpn_keys ADD COLUMN last_activity_at DATETIME"  # noqa: E501
                    )
                )
                await conn.execute(
                    text(
                        "UPDATE vpn_keys SET last_activity_at = generated_at "
                        "WHERE last_activity_at IS NULL"
                    )
                )


@asynccontextmanager  # noqa: E302
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
