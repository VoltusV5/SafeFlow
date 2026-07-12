"""Репозиторий для управления промокодами.

Модуль определяет класс PromocodeRepository для работы с таблицей промокодов в БД.  # noqa: E501
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.promocode import Promocode
from app.db.repositories.base import BaseRepository


class PromocodeRepository(BaseRepository[Promocode]):
    """Репозиторий промокодов.

    Предоставляет методы для получения и валидации скидочных кодов.
    """

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория промокодов.

        Args:
            session: Асинхронная сессия БД.
        """
        super().__init__(Promocode, session)

    async def get_by_code(self, code: str) -> Optional[Promocode]:
        """Получение промокода по его уникальному строковому значению.

        Args:
            code: Строковое значение промокода, введенное пользователем.

        Returns:
            Объект Promocode, если найден, иначе None.
        """
        result = await self.session.execute(
            select(Promocode).filter(Promocode.code == code)
        )
        return result.scalars().first()
