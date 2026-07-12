"""Точка входа FastAPI-приложения SafeFlow VPN."""

import asyncio
from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import api_router
from app.bot.bot_instance import bot, dp
from app.core.config import settings
from app.core.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения FastAPI (старт и остановка)."""
    # Инициализация бота
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if settings.use_webhook:
            webhook_url = f"{settings.bot_webhook_url}{settings.bot_webhook_path}"
            await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
        else:
            try:
                await bot.delete_webhook(drop_pending_updates=True)
            except Exception as e:
                logger.warning(f"Failed to delete webhook: {e}")
            # Запускаем long polling в фоне
            app.state.bot_task = asyncio.create_task(dp.start_polling(bot))
    except Exception as e:
        logger.error(f"Failed to initialize Telegram Bot: {e}")

    yield

    # Остановка бота
    try:
        if settings.use_webhook:
            await bot.delete_webhook()
        else:
            if hasattr(app.state, "bot_task"):
                app.state.bot_task.cancel()
        await bot.session.close()
    except Exception as e:
        logger.error(f"Failed to close Telegram Bot session: {e}")


app = FastAPI(
    title="SafeFlow VPN API",
    version="1.0",
    description="API для управления VPN-подписками, ключами и платежами.",
    lifespan=lifespan
)

# Rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене ограничить список доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.post(settings.bot_webhook_path, include_in_schema=False)
async def bot_webhook(update: dict):
    """Эндпоинт для получения обновлений от Telegram."""
    if settings.use_webhook:
        telegram_update = Update(**update)
        await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}


@app.get("/", tags=["health"])
async def root():
    """Health check эндпоинт."""
    return {"message": "SafeFlow VPN API is running", "status": "ok"}
