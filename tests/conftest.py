"""Конфигурация тестов (pytest).

Модуль содержит общие фикстуры для настройки асинхронного тестового
окружения и базы данных в памяти (SQLite).
"""

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.models import Base

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Создает экземпляр event loop для тестовой сессии.

    Необходимо для корректной работы асинхронных фикстур с областью
    видимости 'session'.

    Yields:
        Тестовый event loop.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    """Создает асинхронный движок SQLAlchemy для тестов.

    Инициализирует SQLite In-Memory базу данных, создает все таблицы
    до начала тестов и удаляет их после завершения сессии.

    Yields:
        Асинхронный движок SQLAlchemy.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine):
    """Генератор тестовых сессий к базе данных.

    Создает новую сессию для каждого теста.

    Args:
        async_engine: Фикстура с асинхронным движком БД.

    Yields:
        Объект асинхронной сессии SQLAlchemy.
    """
    async_session_factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session_factory() as session:
        yield session
