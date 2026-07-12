from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vpn_bot.config import get_settings
from vpn_bot.db.analytics_base import BaseAnalytics

_settings = get_settings()

_engine_kw: dict = {"echo": False}
if "sqlite" in _settings.analytics_database_url.lower():
    _engine_kw["connect_args"] = {"timeout": 30.0}

engine_analytics = create_async_engine(
    _settings.analytics_database_url, **_engine_kw
)  # noqa: E501


@event.listens_for(engine_analytics.sync_engine, "connect")
def _sqlite_analytics_on_connect(dbapi_conn, connection_record) -> None:
    if engine_analytics.dialect.name != "sqlite":
        return
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA busy_timeout=30000")
    finally:
        cur.close()


async_session_maker_analytics = async_sessionmaker(
    engine_analytics,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_analytics_db() -> None:
    from vpn_bot.db import analytics_models as _am  # noqa: F401

    async with engine_analytics.begin() as conn:
        await conn.run_sync(BaseAnalytics.metadata.create_all)
        if "sqlite" in _settings.analytics_database_url.lower():
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))


@asynccontextmanager
async def session_analytics_scope() -> AsyncIterator[AsyncSession]:
    async with async_session_maker_analytics() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
