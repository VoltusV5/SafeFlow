from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.subscription import Subscription
from app.db.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    def __init__(self, session: AsyncSession):
        super().__init__(Subscription, session)

    async def get_active_by_user_id(self, user_id: int) -> Optional[Subscription]:
        result = await self.session.execute(
            select(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.is_active == True
            )
        )
        return result.scalars().first()
