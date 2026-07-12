"""Хендлеры текстовых команд бота."""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from app.bot.keyboards.inline import get_main_menu_keyboard
from app.db.uow import UnitOfWork
from app.schemas.user import UserCreate
from app.services.user_service import UserService

router = Router(name="commands")


@router.message(CommandStart())
async def command_start(message: Message, uow: UnitOfWork):
    """Обработка команды /start.
    
    Регистрирует пользователя (если его нет) и показывает главное меню.

    Args:
        message: Сообщение от пользователя.
        uow: UnitOfWork (внедряется через middleware).
    """
    if message.from_user:
        # Пытаемся зарегистрировать или обновить пользователя
        user_service = UserService(uow)
        
        # Извлекаем параметр рефералки, если он есть (например, /start ref123)
        args = message.text.split() if message.text else []
        referred_by = None
        if len(args) > 1 and args[1].isdigit():
            referred_by = int(args[1])
            
        user_in = UserCreate(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            referred_by=referred_by
        )
        
        await user_service.register_user(user_in)

    text = (
        "👋 <b>Добро пожаловать в SafeFlow VPN!</b>\n\n"
        "Мы предоставляем быстрый и безопасный VPN на современных протоколах "
        "(VLESS / AmneziaWG).\n\n"
        "👇 Нажмите кнопку ниже, чтобы открыть удобное приложение для управления!"
    )
    
    await message.answer(
        text=text,
        reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def command_help(message: Message):
    """Обработка команды /help."""
    text = (
        "ℹ️ <b>Доступные команды:</b>\n\n"
        "/start — Главное меню\n"
        "/help — Справка\n"
        "/profile — Ваш профиль\n"
        "/keys — Список ключей\n"
        "/subscribe — Тарифы\n"
        "/promo — Промокоды\n"
    )
    await message.answer(text=text, parse_mode="HTML")


@router.message(Command("profile"))
async def command_profile(message: Message, uow: UnitOfWork):
    """Обработка команды /profile."""
    from app.bot.handlers.buttons import handle_profile
    # Делегируем логику кнопке (эмулируем CallbackQuery)
    # Так как handle_profile ожидает CallbackQuery, создадим обертку
    user = await uow.users.get_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден. Нажмите /start.")
        return
        
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Баланс:</b> {getattr(user, 'balance', 0)} руб.\n"
    )
    subs = await uow.subscriptions.get_all()
    active_sub = next(
        (s for s in subs if getattr(s, "user_id", None) == user.id and getattr(s, "is_active", False)),
        None
    )
    
    if active_sub:
        expires = getattr(active_sub, 'expires_at', None)
        date_str = expires.strftime("%d.%m.%Y") if expires else "Бессрочно"
        text += f"\n✅ <b>Подписка активна до:</b> {date_str}"
    else:
        text += "\n❌ У вас нет активной подписки."
        
    await message.answer(text=text, parse_mode="HTML")


@router.message(Command("keys", "my"))
async def command_keys(message: Message, uow: UnitOfWork):
    """Обработка команды /keys и /my."""
    user = await uow.users.get_by_tg_id(message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден. Нажмите /start.")
        return
        
    keys = await uow.keys.get_active_by_user_id(user.id)
    if not keys:
        await message.answer("У вас пока нет сгенерированных ключей VPN.")
        return
        
    text = "🔑 <b>Ваши ключи:</b>\n\n"
    for idx, key in enumerate(keys, 1):
        text += f"{idx}. <code>{getattr(key, 'key_data', '')}</code>\n"
        
    await message.answer(text=text, parse_mode="HTML")


@router.message(Command("subscribe"))
async def command_subscribe(message: Message):
    """Обработка команды /subscribe."""
    from app.bot.keyboards.inline import get_tariffs_keyboard
    
    text = (
        "💳 <b>Выберите тариф:</b>\n\n"
        "После выбора тарифа вам будет предложена ссылка на оплату."
    )
    await message.answer(text=text, reply_markup=get_tariffs_keyboard(), parse_mode="HTML")


@router.message(Command("promo"))
async def command_promo(message: Message):
    """Обработка команды /promo."""
    text = (
        "🎁 <b>Активация промокода</b>\n\n"
        "Для активации промокода отправьте мне его сообщением.\n"
        "Функция пока в разработке!"
    )
    await message.answer(text=text, parse_mode="HTML")
