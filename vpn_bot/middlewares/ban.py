from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, Update

from vpn_bot.db.models import User


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("db_user")
        if user is None or not user.is_banned:
            return await handler(event, data)

        text = "Доступ заблокирован. Если это ошибка, свяжитесь с администратором."  # noqa: E501
        if isinstance(event, Update):
            if event.message:
                await event.message.answer(text)
            elif event.callback_query and isinstance(
                event.callback_query.message, Message
            ):
                await event.callback_query.answer(text, show_alert=True)
            elif event.pre_checkout_query:
                await event.pre_checkout_query.answer(
                    ok=False,
                    error_message="Доступ к боту заблокирован.",
                )
        return None
