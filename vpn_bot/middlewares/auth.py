from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from vpn_bot.services.user_service import UserService


def _tg_from_update(update: Update):
    if update.message:
        return update.message.from_user
    if update.callback_query:
        return update.callback_query.from_user
    if update.edited_message:
        return update.edited_message.from_user
    if update.pre_checkout_query:
        return update.pre_checkout_query.from_user
    return None


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        update = event
        tg_user = _tg_from_update(update)
        session = data["session"]
        if tg_user is None:
            data["db_user"] = None
            return await handler(event, data)

        us = UserService(session)
        data["db_user"] = await us.get_or_create(tg_user.id, tg_user.username)
        return await handler(event, data)
