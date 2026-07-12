from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.db.models import User


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_tg_id(self, tg_id: int) -> User | None:
        r = await self._s.execute(select(User).where(User.tg_id == tg_id))
        return r.scalar_one_or_none()

    async def get_or_create(self, tg_id: int, tg_username: str | None) -> User:
        user = await self.get_by_tg_id(tg_id)
        if user:
            if tg_username is not None and user.tg_username != tg_username:
                user.tg_username = tg_username
            return user
        user = User(tg_id=tg_id, tg_username=tg_username)
        self._s.add(user)
        await self._s.flush()
        return user

    async def set_password_ok(self, user: User) -> None:
        user.password_entered = True
        user.password_fail_attempts = 0
        if user.first_password_ok_at is None:
            user.first_password_ok_at = datetime.now(UTC)
        await self._s.flush()

    async def register_password_fail(self, user: User) -> int:
        user.password_fail_attempts = int(user.password_fail_attempts or 0) + 1
        await self._s.flush()
        return user.password_fail_attempts

    async def reset_password_failures(self, tg_id: int) -> User | None:
        user = await self.get_by_tg_id(tg_id)
        if not user:
            return None
        user.password_fail_attempts = 0
        await self._s.flush()
        return user

    async def set_banned(self, tg_id: int, banned: bool) -> User | None:
        user = await self.get_by_tg_id(tg_id)
        if not user:
            return None
        user.is_banned = banned
        await self._s.flush()
        return user

    async def ban_by_username(self, username: str, banned: bool) -> User | None:  # noqa: E501
        clean = username.lstrip("@").lower()
        r = await self._s.execute(select(User))
        for u in r.scalars().all():
            if u.tg_username and u.tg_username.lower() == clean:
                u.is_banned = banned
                await self._s.flush()
                return u
        return None

    async def list_authorized_users(self) -> list[User]:
        r = await self._s.execute(
            select(User).where(User.password_entered.is_(True), User.is_banned.is_(False))  # noqa: E501
        )
        return list(r.scalars().all())

    async def list_all_users(self) -> list[User]:
        r = await self._s.execute(select(User))
        return list(r.scalars().all())

    async def find_by_username(self, username: str) -> User | None:
        clean = username.lstrip("@").lower()
        r = await self._s.execute(select(User))
        for u in r.scalars().all():
            if u.tg_username and u.tg_username.lower() == clean:
                return u
        return None
