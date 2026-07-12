"""Настройки подключения к Redis."""

import redis.asyncio as redis
from app.core.config import settings

# Глобальный асинхронный клиент Redis
redis_client = redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True
)

async def get_redis():
    """Dependency для получения клиента Redis."""
    return redis_client
