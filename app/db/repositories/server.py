"""Репозиторий для управления серверами.

Модуль определяет класс ServerRepository для работы с таблицей серверов в БД.
"""

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.server import Server
from app.db.repositories.base import BaseRepository


class ServerRepository(BaseRepository[Server]):
    """Репозиторий серверов.

    Предоставляет методы для поиска доступных VPN серверов (нод).
    """

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория серверов.

        Args:
            session: Асинхронная сессия БД.
        """
        super().__init__(Server, session)

    async def get_active_servers(self) -> List[Server]:
        """Получение списка всех активных серверов.

        Активные сервера могут использоваться для выдачи новых ключей.

        Returns:
            Список активных объектов Server.
        """
        result = await self.session.execute(
            select(Server).filter(Server.is_active.is_(True))
        )
        return list(result.scalars().all())
