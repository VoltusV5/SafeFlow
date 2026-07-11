import secrets

from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove

from vpn_bot.config import get_settings
from vpn_bot.constants import MAX_PASSWORD_FAIL_ATTEMPTS
from vpn_bot.db.models import User
from vpn_bot.filters import GuestFilter
from vpn_bot.keyboards import main_menu_kb
from vpn_bot.services.user_service import UserService

router = Router(name="guest")
_guest = GuestFilter()


@router.message(_guest, F.text & ~F.text.startswith("/"))
async def try_password(message: Message, db_user: User, session) -> None:
    fails = int(db_user.password_fail_attempts or 0)
    if fails >= MAX_PASSWORD_FAIL_ATTEMPTS:
        await message.answer(
            "Слишком много неверных попыток ввода пароля. "
            "Новые попытки недоступны — обратитесь к администратору."
        )
        return

    entered = message.text.strip() if message.text else ""
    ok = secrets.compare_digest(entered, get_settings().bot_password)
    if not ok:
        n = await UserService(session).register_password_fail(db_user)
        if n >= MAX_PASSWORD_FAIL_ATTEMPTS:
            await message.answer(
                "Достигнут лимит неверных попыток. Пароль больше не принимается. "
                "Обратитесь к администратору."
            )
        else:
            await message.answer("Неверный пароль. Попробуйте ещё раз.")
        return

    await UserService(session).set_password_ok(db_user)
    await message.answer(
        "Пароль принят.\n\n"
        "Сервис предназначен исключительно для законных целей в соответствии с "
        "законодательством РФ. Мы не поддерживаем и не поощряем использование для "
        "доступа к запрещённым ресурсам или нарушения закона.",
        reply_markup=main_menu_kb(),
    )


@router.message(_guest, F.text.startswith("/"))
async def guest_blocked_command(message: Message) -> None:
    await message.answer(
        "Сначала введите пароль доступа обычным сообщением (не командой).",
        reply_markup=ReplyKeyboardRemove(),
    )
