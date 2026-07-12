from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import KeyStatus
from app.db.models.key import Key
from app.db.repositories.base import BaseRepository


class KeyRepository(BaseRepository[Key]):
    def __init__(self, session: AsyncSession):
        super().__init__(Key, session)

    async def get_by_user_id(self, user_id: int) -> List[Key]:
        """Возвращает все ключи пользователя."""
        result = await self.session.execute(
            select(Key).filter(Key.user_id == user_id)
        )
        return list(result.scalars().all())

    # Алиас для обратной совместимости с mock-репозиторием
    async def get_by_user(self, user_id: int) -> List[Key]:
        """Алиас для get_by_user_id."""
        return await self.get_by_user_id(user_id)

    async def get_active_by_user_id(self, user_id: int) -> List[Key]:
        """Возвращает только активные ключи пользователя."""
        result = await self.session.execute(
            select(Key).filter(
                Key.user_id == user_id,
                Key.status == KeyStatus.ACTIVE
            )
        )
        return list(result.scalars().all())
