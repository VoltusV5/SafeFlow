"""Репозиторий для управления заявками на возврат.

Модуль определяет класс RefundTicketRepository для работы с таблицей тикетов возврата.  # noqa: E501
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refund_ticket import RefundTicket
from app.db.repositories.base import BaseRepository


class RefundTicketRepository(BaseRepository[RefundTicket]):
    """Репозиторий заявок на возврат (тикетов).

    Предоставляет методы для поиска открытых и завершенных возвратов.
    """

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория тикетов возврата.

        Args:
            session: Асинхронная сессия БД.
        """
        super().__init__(RefundTicket, session)

    async def get_by_user_id(self, user_id: int) -> List[RefundTicket]:
        """Получение всех заявок на возврат конкретного пользователя.

        Args:
            user_id: Внутренний идентификатор пользователя в базе данных.

        Returns:
            Список объектов RefundTicket, принадлежащих пользователю.
        """
        result = await self.session.execute(
            select(RefundTicket).filter(RefundTicket.user_id == user_id)
        )
        return list(result.scalars().all())
