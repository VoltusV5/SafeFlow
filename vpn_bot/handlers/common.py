from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from vpn_bot.db.models import User
from vpn_bot.keyboards import main_menu_kb

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User, state: FSMContext) -> None:  # noqa: E501
    await state.clear()
    if db_user.password_entered:
        await message.answer(
            "Главное меню. Выберите действие кнопкой ниже или командой.",
            reply_markup=main_menu_kb(),
        )
        return

    await message.answer(
        "Добро пожаловать.\n\n"
        "Этот бот выдаёт ключи. Чтобы продолжить, "
        "отправьте пароль доступа.",
        reply_markup=ReplyKeyboardRemove(),
    )
