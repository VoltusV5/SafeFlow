from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.payment import Payment
from app.db.repositories.base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session: AsyncSession):
        super().__init__(Payment, session)

    async def get_by_user_id(self, user_id: int) -> List[Payment]:
        result = await self.session.execute(select(Payment).filter(Payment.user_id == user_id))
        return list(result.scalars().all())
