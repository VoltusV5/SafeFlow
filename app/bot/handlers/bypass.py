from aiogram import Router, types
from aiogram.filters import Command

router = Router(name="bypass_router")

@router.message(Command("bypass"))
async def cmd_bypass(message: types.Message):
    """
    Хендлер для команды /bypass.
    Здесь второй разработчик может добавить меню для настройки роутинга.
    """
    await message.answer(
        "Настройки обхода блокировок.\n"
        "Эта секция находится в разработке."
    )
