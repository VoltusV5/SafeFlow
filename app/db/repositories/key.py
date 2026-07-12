"""Репозиторий для управления VPN-ключами.

Модуль определяет класс KeyRepository для работы с таблицей ключей в БД.
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.key import Key
from app.db.repositories.base import BaseRepository


class KeyRepository(BaseRepository[Key]):
    """Репозиторий ключей.

    Предоставляет методы для поиска и управления VPN конфигурациями пользователей.  # noqa: E501
    """

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория ключей.

        Args:
            session: Асинхронная сессия БД.
        """
        super().__init__(Key, session)

    async def get_by_user_id(self, user_id: int) -> List[Key]:
        """Получение всех ключей конкретного пользователя.

        Args:
            user_id: Внутренний идентификатор пользователя в базе данных.

        Returns:
            Список объектов Key, принадлежащих пользователю.
        """
        result = await self.session.execute(
            select(Key).filter(Key.user_id == user_id)
        )
        return list(result.scalars().all())
