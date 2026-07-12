"""Генерация клавиатур для бота."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.core.config import settings


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Создает главную клавиатуру с кнопкой Web App.

    Returns:
        InlineKeyboardMarkup: Клавиатура с кнопкой Web App и базовым меню.
    """
    builder = InlineKeyboardBuilder()

    # Кнопка для открытия Telegram Web App
    builder.row(
        InlineKeyboardButton(
            text="🚀 Открыть приложение",
            web_app={"url": settings.webapp_url}
        )
    )

    # Дополнительные кнопки (опционально, если пользователь не хочет открывать TWA)
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="🔑 Мои ключи", callback_data="keys")
    )
    builder.row(
        InlineKeyboardButton(text="💳 Тарифы", callback_data="tariffs"),
        InlineKeyboardButton(text="💬 Поддержка", url="https://t.me/admin")
    )

    return builder.as_markup()


def get_tariffs_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с выбором тарифов.
    
    Returns:
        InlineKeyboardMarkup: Клавиатура с тарифами.
    """
    builder = InlineKeyboardBuilder()
    
    # В реальном приложении цены стоит брать из базы или конфига
    builder.row(
        InlineKeyboardButton(text="Базовый (100 ₽ / мес)", callback_data="buy_plan_base")
    )
    builder.row(
        InlineKeyboardButton(text="PRO (150 ₽ / мес)", callback_data="buy_plan_pro")
    )
    
    return builder.as_markup()
