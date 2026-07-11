from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.config import get_settings
from vpn_bot.constants import AMNEZIA_WG_RATE_LIMIT_HOURS
from vpn_bot.db.models import User, VpnKey
from vpn_bot.enums import VpnProtocol
from vpn_bot.exceptions import TooManyKeysError
from vpn_bot.services.protocol_generators import GeneratedVpnConfig, generate_for_protocol


class KeyService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_active_for_user(self, user_id: int) -> list[VpnKey]:
        r = await self._s.execute(
            select(VpnKey).where(
                VpnKey.user_id == user_id,
                VpnKey.is_active.is_(True),
            )
        )
        return list(r.scalars().all())

    async def count_active_by_protocol(self, user_id: int) -> dict[str, int]:
        r = await self._s.execute(
            select(VpnKey.protocol, func.count())
            .where(
                VpnKey.user_id == user_id,
                VpnKey.is_active.is_(True),
            )
            .group_by(VpnKey.protocol)
        )
        return {row[0]: int(row[1]) for row in r.all()}

    async def deactivate_user_keys(self, user_id: int) -> None:
        from vpn_bot.services.revocation_service import revoke_key_on_server
        r = await self._s.execute(select(VpnKey).where(VpnKey.user_id == user_id, VpnKey.is_active.is_(True)))
        keys = r.scalars().all()
        for k in keys:
            await revoke_key_on_server(k)
        await self._s.execute(
            update(VpnKey)
            .where(VpnKey.user_id == user_id, VpnKey.is_active.is_(True))
            .values(is_active=False)
        )
        await self._s.flush()

    async def deactivate_all_active_keys(self) -> None:
        from vpn_bot.services.revocation_service import revoke_key_on_server
        r = await self._s.execute(select(VpnKey).where(VpnKey.is_active.is_(True)))
        keys = r.scalars().all()
        for k in keys:
            await revoke_key_on_server(k)
        await self._s.execute(
            update(VpnKey).where(VpnKey.is_active.is_(True)).values(is_active=False)
        )
        await self._s.flush()

    async def count_amnezia_keys_last_24h(self, user_id: int) -> int:
        since = datetime.now(UTC) - timedelta(hours=AMNEZIA_WG_RATE_LIMIT_HOURS)
        r = await self._s.execute(
            select(func.count())
            .select_from(VpnKey)
            .where(
                VpnKey.user_id == user_id,
                VpnKey.protocol == VpnProtocol.AMNEZIA_WG.value,
                VpnKey.generated_at >= since,
            )
        )
        return int(r.scalar_one() or 0)

    async def deactivate_user_keys_for_protocol(
        self, user_id: int, protocol: VpnProtocol
    ) -> None:
        from vpn_bot.services.revocation_service import revoke_key_on_server
        r = await self._s.execute(
            select(VpnKey).where(
                VpnKey.user_id == user_id,
                VpnKey.protocol == protocol.value,
                VpnKey.is_active.is_(True),
            )
        )
        keys = r.scalars().all()
        for k in keys:
            await revoke_key_on_server(k)
        await self._s.execute(
            update(VpnKey)
            .where(
                VpnKey.user_id == user_id,
                VpnKey.protocol == protocol.value,
                VpnKey.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self._s.flush()

    async def create_key(self, user: User, protocol: VpnProtocol, custom_name: str | None = None) -> VpnKey:
        hint = custom_name or user.tg_username or str(user.tg_id)
        cfg = await generate_for_protocol(protocol, hint)
        return await self.create_key_from_generated(user, protocol, cfg, custom_name)

    async def create_key_from_generated(
        self,
        user: User,
        protocol: VpnProtocol,
        cfg: GeneratedVpnConfig,
        custom_name: str | None = None,
    ) -> VpnKey:
        now = datetime.now(UTC)
        row = VpnKey(
            user_id=user.id,
            protocol=protocol.value,
            config_filename=cfg.filename,
            key_value=cfg.key_value,
            is_active=True,
            generated_at=now,
            regenerated_at=None,
            wg_peer_public_key=cfg.wg_peer_public_key,
            custom_name=custom_name,
        )
        self._s.add(row)
        await self._s.flush()
        return row

    async def generate_one(self, user: User, protocol: VpnProtocol, custom_name: str | None = None) -> VpnKey:
        settings = get_settings()
        if (
            protocol == VpnProtocol.AMNEZIA_WG
            and settings.generate_peer_script.strip()
            and not custom_name
        ):
            lim = settings.max_amnezia_keys_per_24h
            n = await self.count_amnezia_keys_last_24h(user.id)
            if n >= lim:
                raise TooManyKeysError(lim, AMNEZIA_WG_RATE_LIMIT_HOURS)
        # REPLACE_ACTIVE_KEY_ON_NEW=true — пометить старые ключи этого протокола в БД неактивными.
        # На сервере Amnezia peer/сертификаты не удаляются. По умолчанию false — все ключи остаются активными.
        if settings.replace_active_key_on_new and not custom_name:
            await self.deactivate_user_keys_for_protocol(user.id, protocol)
        return await self.create_key(user, protocol, custom_name)

    async def generate_one_from_provided(
        self,
        user: User,
        protocol: VpnProtocol,
        cfg: GeneratedVpnConfig,
        custom_name: str | None = None,
    ) -> VpnKey:
        """Как generate_one, но конфиг уже сгенерирован снаружи (например /raw_config)."""
        settings = get_settings()
        if (
            protocol == VpnProtocol.AMNEZIA_WG
            and settings.generate_peer_script.strip()
            and not custom_name
        ):
            lim = settings.max_amnezia_keys_per_24h
            n = await self.count_amnezia_keys_last_24h(user.id)
            if n >= lim:
                raise TooManyKeysError(lim, AMNEZIA_WG_RATE_LIMIT_HOURS)
        if settings.replace_active_key_on_new and not custom_name:
            await self.deactivate_user_keys_for_protocol(user.id, protocol)
        return await self.create_key_from_generated(user, protocol, cfg, custom_name)
