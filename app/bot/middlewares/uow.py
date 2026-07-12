"""Middleware для внедрения UnitOfWork в хендлеры бота."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.uow import UnitOfWork


class UoWMiddleware(BaseMiddleware):
    """Middleware для управления контекстом базы данных.

    Создает экземпляр UnitOfWork для каждого обновления (Update) и передает его
    в хендлер. При завершении хендлера автоматически закрывает сессию БД.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Перехватывает событие и внедряет UoW.

        Args:
            handler: Следующий хендлер в цепочке.
            event: Событие от Telegram (Message, CallbackQuery и т.д.).
            data: Данные контекста FSM и другие внедренные зависимости.

        Returns:
            Результат выполнения хендлера.
        """
        async with UnitOfWork() as uow:
            data["uow"] = uow
            return await handler(event, data)
