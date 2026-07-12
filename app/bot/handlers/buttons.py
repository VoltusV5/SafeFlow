"""Хендлеры для инлайн-кнопок (CallbackQuery)."""

from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.db.uow import UnitOfWork

router = Router(name="buttons")


@router.callback_query(F.data == "profile")
async def handle_profile(callback: CallbackQuery, uow: UnitOfWork):
    """Обработка кнопки 'Профиль'."""
    await callback.answer()
    
    user = await uow.users.get_by_tg_id(callback.from_user.id)
    if not user:
        await callback.message.answer("Пользователь не найден. Нажмите /start.")
        return
        
    text = (
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Баланс:</b> {getattr(user, 'balance', 0)} руб.\n"
    )
    
    # Ищем активную подписку
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
        
    await callback.message.answer(text=text, parse_mode="HTML")


@router.callback_query(F.data == "keys")
async def handle_keys(callback: CallbackQuery, uow: UnitOfWork):
    """Обработка кнопки 'Мои ключи'."""
    await callback.answer()
    
    user = await uow.users.get_by_tg_id(callback.from_user.id)
    if not user:
        await callback.message.answer("Пользователь не найден. Нажмите /start.")
        return
        
    keys = await uow.keys.get_active_by_user_id(user.id)
    
    if not keys:
        await callback.message.answer("У вас пока нет сгенерированных ключей VPN.")
        return
        
    text = "🔑 <b>Ваши ключи:</b>\n\n"
    for idx, key in enumerate(keys, 1):
        text += f"{idx}. <code>{getattr(key, 'key_data', '')}</code>\n"
        
    await callback.message.answer(text=text, parse_mode="HTML")


@router.callback_query(F.data == "tariffs")
async def handle_tariffs(callback: CallbackQuery):
    """Обработка кнопки 'Тарифы'."""
    from app.bot.keyboards.inline import get_tariffs_keyboard
    await callback.answer()
    
    text = (
        "💳 <b>Выберите тариф:</b>\n\n"
        "После выбора тарифа вам будет предложена ссылка на оплату."
    )
    await callback.message.answer(text=text, reply_markup=get_tariffs_keyboard(), parse_mode="HTML")


@router.callback_query(F.data.startswith("buy_plan_"))
async def handle_buy_plan(callback: CallbackQuery, uow: UnitOfWork):
    """Обработка нажатия на конкретный тариф."""
    await callback.answer()
    
    plan_name = callback.data.split("_")[2].upper()
    
    user = await uow.users.get_by_tg_id(callback.from_user.id)
    if not user:
        await callback.message.answer("Пользователь не найден. Нажмите /start.")
        return
        
    # В реальном приложении здесь будет генерация ссылки через aaio_service
    # Пока что выдаем заглушку
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    amount = 100 if plan_name == "BASE" else 150
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Оплатить {amount} ₽", url="https://aaio.so/pay/demo")]
    ])
    
    await callback.message.answer(
        text=f"Вы выбрали тариф <b>{plan_name}</b>.\nСумма к оплате: {amount} руб.\n\nНажмите кнопку ниже для оплаты:",
        reply_markup=markup,
        parse_mode="HTML"
    )
