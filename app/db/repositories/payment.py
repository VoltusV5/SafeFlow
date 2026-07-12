"""Репозиторий для управления платежами.

Модуль определяет класс PaymentRepository для работы с таблицей платежей в БД.
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import Payment
from app.db.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    """Репозиторий платежей.

    Предоставляет методы для получения истории транзакций пользователей.
    """

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория платежей.

        Args:
            session: Асинхронная сессия БД.
        """
        super().__init__(Payment, session)

    async def get_by_user_id(self, user_id: int) -> List[Payment]:
        """Получение всех платежей конкретного пользователя.

        Args:
            user_id: Внутренний идентификатор пользователя в базе данных.

        Returns:
            Список объектов Payment, принадлежащих пользователю.
        """
        result = await self.session.execute(
            select(Payment).filter(Payment.user_id == user_id)
        )
        return list(result.scalars().all())
