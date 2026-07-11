from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.db.models import StarDonationSubscription, StarPayment, User


class StarDonationService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record_star_payment(
        self,
        user_id: int,
        stars: int,
        monthly_pledge: bool,
        telegram_charge_id: str,
    ) -> bool:
        r = await self._s.execute(
            select(StarPayment.id).where(
                StarPayment.telegram_charge_id == telegram_charge_id
            )
        )
        if r.scalar_one_or_none() is not None:
            return False
        self._s.add(
            StarPayment(
                user_id=user_id,
                stars_amount=stars,
                monthly_pledge=monthly_pledge,
                telegram_charge_id=telegram_charge_id,
            )
        )
        await self._s.flush()
        return True

    async def upsert_monthly(self, user_id: int, stars: int) -> None:
        now = datetime.now(UTC)
        nxt = now + timedelta(days=30)
        r = await self._s.execute(
            select(StarDonationSubscription).where(
                StarDonationSubscription.user_id == user_id
            )
        )
        row = r.scalar_one_or_none()
        if row:
            row.stars_amount = stars
            row.next_reminder_at = nxt
            row.is_active = True
        else:
            self._s.add(
                StarDonationSubscription(
                    user_id=user_id,
                    stars_amount=stars,
                    next_reminder_at=nxt,
                    is_active=True,
                )
            )
        await self._s.flush()

    async def deactivate_for_user(self, user_id: int) -> bool:
        r = await self._s.execute(
            select(StarDonationSubscription).where(
                StarDonationSubscription.user_id == user_id
            )
        )
        row = r.scalar_one_or_none()
        if not row or not row.is_active:
            return False
        row.is_active = False
        await self._s.flush()
        return True

    async def list_due(self, before: datetime) -> list[tuple[int, int, int]]:
        r = await self._s.execute(
            select(StarDonationSubscription.id, User.tg_id, StarDonationSubscription.stars_amount)
            .join(User, User.id == StarDonationSubscription.user_id)
            .where(
                StarDonationSubscription.is_active.is_(True),
                StarDonationSubscription.next_reminder_at <= before,
            )
        )
        return [(int(a), int(b), int(c)) for a, b, c in r.all()]

    async def bump_reminder(self, subscription_id: int) -> None:
        row = await self._s.get(StarDonationSubscription, subscription_id)
        if not row or not row.is_active:
            return
        row.next_reminder_at = datetime.now(UTC) + timedelta(days=30)
        await self._s.flush()
