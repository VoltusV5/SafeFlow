"""Управление сессиями базы данных.

Модуль отвечает за создание асинхронного движка SQLAlchemy и генерацию сессий.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Асинхронный движок для подключения к PostgreSQL
engine = create_async_engine(settings.database_url, echo=False)

# Фабрика для создания новых асинхронных сессий
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db():
    """Генератор сессий базы данных (Dependency).

    Создает новую сессию для каждого запроса и автоматически закрывает её
    после завершения.

    Yields:
        AsyncSession: Объект асинхронной сессии SQLAlchemy.
    """
    async with AsyncSessionLocal() as session:
        yield session
