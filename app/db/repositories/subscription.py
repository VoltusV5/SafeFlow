"""Репозиторий для управления подписками.

Модуль определяет класс SubscriptionRepository для работы с таблицей подписок в БД.  # noqa: E501
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.subscription import Subscription
from app.db.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    """Репозиторий подписок.

    Предоставляет методы для поиска активных подписок пользователей.
    """

    def __init__(self, session: AsyncSession):
        """Инициализация репозитория подписок.

        Args:
            session: Асинхронная сессия БД.
        """
        super().__init__(Subscription, session)

    async def get_active_by_user_id(
        self, user_id: int
    ) -> Optional[Subscription]:
        """Получение активной подписки по идентификатору пользователя.

        Args:
            user_id: Внутренний идентификатор пользователя в базе данных.

        Returns:
            Объект активной Subscription, если найдена, иначе None.
        """
        result = await self.session.execute(
            select(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.is_active.is_(True),
            )
        )
        return result.scalars().first()
