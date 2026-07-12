from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.promocode import Promocode
from app.db.repositories.base import BaseRepository


class PromocodeRepository(BaseRepository[Promocode]):
    def __init__(self, session: AsyncSession):
        super().__init__(Promocode, session)

    async def get_by_code(self, code: str) -> Optional[Promocode]:
        result = await self.session.execute(select(Promocode).filter(Promocode.code == code))
        return result.scalars().first()
