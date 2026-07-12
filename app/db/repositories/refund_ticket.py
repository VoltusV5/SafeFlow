from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refund_ticket import RefundTicket
from app.db.repositories.base import BaseRepository


class RefundTicketRepository(BaseRepository[RefundTicket]):
    def __init__(self, session: AsyncSession):
        super().__init__(RefundTicket, session)

    async def get_by_user_id(self, user_id: int) -> List[RefundTicket]:
        result = await self.session.execute(select(RefundTicket).filter(RefundTicket.user_id == user_id))
        return list(result.scalars().all())
