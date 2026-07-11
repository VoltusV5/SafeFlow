from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from vpn_bot.config import get_settings
from vpn_bot.db.models import User


class AuthedFilter(Filter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        db_user: User | None,
    ) -> bool:
        return db_user is not None and db_user.password_entered


class GuestFilter(Filter):
    async def __call__(
        self,
        event: Message | CallbackQuery,
        db_user: User | None,
    ) -> bool:
        return db_user is not None and not db_user.password_entered


class AdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        uid = event.from_user.id if event.from_user else 0
        return uid in get_settings().admin_ids
