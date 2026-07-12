"""Опциональное удаление давно неактивных WG-ключей из БД (по last_activity_at на awg).  # noqa: E501

При STALE_WG_KEY_DAYS=0 вызов ничего не делает — ключи остаются для вернувшихся пользователей.  # noqa: E501
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.db.models import VpnKey


async def purge_stale_wg_keys(session: AsyncSession, stale_days: int) -> int:
    """
    Удаляет активные ключи с заполненным wg_peer_public_key, у которых
    last_activity_at старше stale_days (или NULL и generated_at старше порога).
    OpenVPN/IPsec и т.д. не трогаем: у них нет awg-активности в логгере.
    """
    if stale_days < 1:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=stale_days)
    r = await session.execute(
        select(VpnKey).where(
            VpnKey.is_active.is_(True),
            VpnKey.wg_peer_public_key.isnot(None),
            VpnKey.wg_peer_public_key != "",
            or_(
                and_(VpnKey.last_activity_at.is_(None), VpnKey.generated_at < cutoff),  # noqa: E501
                and_(
                    VpnKey.last_activity_at.isnot(None),
                    VpnKey.last_activity_at < cutoff,
                ),
            ),
        )
    )
    keys = r.scalars().all()
    if not keys:
        return 0
    from vpn_bot.services.revocation_service import revoke_key_on_server
    for k in keys:
        await revoke_key_on_server(k)
    ids = [k.id for k in keys]
    await session.execute(delete(VpnKey).where(VpnKey.id.in_(ids)))
    return len(ids)
