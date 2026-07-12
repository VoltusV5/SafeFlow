"""Репозиторий для управления пользователями.

Модуль определяет класс UserRepository для работы с таблицей пользователей в БД.  # noqa: E501
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Репозиторий пользователей.

    Предоставляет методы для поиска и управления пользователями Telegram.
    """

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория пользователей.

        Args:
            session: Асинхронная сессия БД.
        """
        super().__init__(User, session)

    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        """Получение пользователя по его Telegram ID.

        Args:
            tg_id: Уникальный идентификатор пользователя в Telegram.

        Returns:
            Объект User, если найден, иначе None.
        """
        result = await self.session.execute(
            select(User).filter(User.tg_id == tg_id)
        )
        return result.scalars().first()
