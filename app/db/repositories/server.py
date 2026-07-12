from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.server import Server
from app.db.repositories.base import BaseRepository


class ServerRepository(BaseRepository[Server]):
    def __init__(self, session: AsyncSession):
        super().__init__(Server, session)

    async def get_active_servers(self) -> List[Server]:
        result = await self.session.execute(select(Server).filter(Server.is_active == True))
        return list(result.scalars().all())
