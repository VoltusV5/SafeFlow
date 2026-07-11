from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from vpn_bot.db.session import async_session_maker
from vpn_bot.db.session_analytics import async_session_maker_analytics


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_maker_analytics() as session_analytics:
            async with async_session_maker() as session:
                data["session"] = session
                data["session_analytics"] = session_analytics
                try:
                    result = await handler(event, data)
                    await session.commit()
                    await session_analytics.commit()
                    return result
                except Exception:
                    await session.rollback()
                    await session_analytics.rollback()
                    raise
