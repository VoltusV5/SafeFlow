from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.db.models import Notification
from vpn_bot.enums import NotificationStatus


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def log_broadcast(
        self,
        *,
        body: str,
        ok: bool,
        admin_user_id: int | None = None,
    ) -> None:
        row = Notification(
            user_id=admin_user_id,
            body=body[:4096],
            scheduled_date=None,
            sent_at=datetime.now(UTC),
            status=NotificationStatus.SENT if ok else NotificationStatus.FAILED,  # noqa: E501
        )
        self._s.add(row)
