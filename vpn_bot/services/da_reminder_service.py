from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.db.models import DonationAlertsSubscription, User


class DonationAlertsReminderService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert_monthly(self, user_id: int) -> None:
        now = datetime.now(UTC)
        nxt = now + timedelta(days=30)
        r = await self._s.execute(
            select(DonationAlertsSubscription).where(
                DonationAlertsSubscription.user_id == user_id
            )
        )
        row = r.scalar_one_or_none()
        if row:
            row.next_reminder_at = nxt
            row.is_active = True
        else:
            self._s.add(
                DonationAlertsSubscription(
                    user_id=user_id,
                    next_reminder_at=nxt,
                    is_active=True,
                )
            )
        await self._s.flush()

    async def deactivate_for_user(self, user_id: int) -> bool:
        r = await self._s.execute(
            select(DonationAlertsSubscription).where(
                DonationAlertsSubscription.user_id == user_id
            )
        )
        row = r.scalar_one_or_none()
        if not row or not row.is_active:
            return False
        row.is_active = False
        await self._s.flush()
        return True

    async def list_due(self, before: datetime) -> list[tuple[int, int]]:
        r = await self._s.execute(
            select(DonationAlertsSubscription.id, User.tg_id)
            .join(User, User.id == DonationAlertsSubscription.user_id)
            .where(
                DonationAlertsSubscription.is_active.is_(True),
                DonationAlertsSubscription.next_reminder_at <= before,
            )
        )
        return [(int(a), int(b)) for a, b in r.all()]

    async def bump_reminder(self, subscription_id: int) -> None:
        row = await self._s.get(DonationAlertsSubscription, subscription_id)
        if not row or not row.is_active:
            return
        row.next_reminder_at = datetime.now(UTC) + timedelta(days=30)
        await self._s.flush()
