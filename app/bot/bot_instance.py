"""Инициализация Telegram бота и диспетчера."""

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot.handlers import buttons, commands
from app.bot.middlewares.uow import UoWMiddleware
from app.core.config import settings

# Инициализируем бота
bot = Bot(
    token=settings.bot_token.get_secret_value(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Инициализируем диспетчер
dp = Dispatcher()

# Подключаем middlewares
dp.update.middleware(UoWMiddleware())

# Подключаем роутеры (хендлеры)
dp.include_router(commands.router)
dp.include_router(buttons.router)
