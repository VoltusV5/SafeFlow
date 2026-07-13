"""Сервис для управления VPN ключами и серверами.

Модуль определяет класс VpnManagerService для аллокации IP-адресов,
выпуска конфигураций и балансировки нагрузки на серверы.
"""

import base64
import ipaddress
import uuid
from typing import Optional

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519

from app.core.config import settings
from app.core.enums import KeyStatus, Protocol
from app.db.uow import UnitOfWork
from app.schemas.vpn import KeyResponse


class VpnManagerService:
    """Сервис для работы с VPN."""

    def __init__(self, uow: UnitOfWork):
        """Инициализация сервиса.

        Args:
            uow: Интерфейс Unit of Work.
        """
        self.uow = uow

    async def _allocate_ip(self, server_id: int) -> str:
        """Аллоцирует первый свободный IP-адрес для сервера.

        Вызывается внутри UoW.

        Args:
            server_id: ID сервера.

        Returns:
            Свободный IPv4 адрес.

        Raises:
            RuntimeError: Если нет свободных IP-адресов.
        """
        network = ipaddress.IPv4Network("10.8.0.0/24")

        all_keys = await self.uow.keys.get_all()
        used_ips = {
            k.internal_ip
            for k in all_keys
            if getattr(k, "server_id", None) == server_id and getattr(
                k, "internal_ip", None)
        }

        # Начинаем со второго адреса (первый - шлюз)
        for ip in network.hosts():
            ip_str = str(ip)
            if ip_str == "10.8.0.1":
                continue
            if ip_str not in used_ips:
                return ip_str

        raise RuntimeError("Нет свободных IP-адресов на сервере.")

    async def allocate_ip(self, server_id: int) -> str:
        """Публичный метод: аллоцирует свободный IP для сервера.

        Открывает собственный UoW-контекст. Не вызывать внутри другого UoW.

        Args:
            server_id: ID сервера.

        Returns:
            Свободный IPv4 адрес.
        """
        async with self.uow:
            return await self._allocate_ip(server_id)

    async def create_key(
        self, user_id: int, server_id: int, protocol: Protocol
    ) -> KeyResponse:
        """Создает новый VPN ключ.

        Args:
            user_id: ID владельца.
            server_id: ID выбранного сервера.
            protocol: Выбранный протокол.

        Returns:
            Схема с данными нового ключа.

        Raises:
            ValueError: Если сервер не найден.
        """
        async with self.uow:
            server = await self.uow.servers.get(server_id)
            if not server:
                raise ValueError("Сервер не найден")

            internal_ip: Optional[str] = None
            client_uuid: Optional[str] = None

            server_ip = getattr(server, 'ip_address', '127.0.0.1')
            agent_url = f"http://{server_ip}:8081/api/keys"
            agent_token = getattr(settings, 'AGENT_TOKEN', 'supersecret')
            headers = {"Authorization": f"Bearer {agent_token}"}

            if protocol == Protocol.AWG:
                internal_ip = await self._allocate_ip(server_id)

                # Генерируем ключи WireGuard
                private_key = x25519.X25519PrivateKey.generate()
                public_key = private_key.public_key()

                priv_b64 = base64.b64encode(private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                )).decode('utf-8')

                pub_b64 = base64.b64encode(public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )).decode('utf-8')

                # Запрос к агенту
                async with httpx.AsyncClient() as client:
                    try:
                        resp = await client.post(
                            f"{agent_url}/awg",
                            json={
                                "public_key": pub_b64,
                                "allowed_ip": f"{internal_ip}/32"
                            },
                            headers=headers,
                            timeout=5.0
                        )
                        if resp.status_code != 200:
                            raise ValueError(f"Agent error: {resp.text}")
                    except httpx.RequestError as e:
                        print(f"Failed to connect to agent: {e}")

                config_data = (
                    f"[Interface]\n"
                    f"PrivateKey = {priv_b64}\n"
                    f"Address = {internal_ip}/24\n"
                    f"[Peer]\n"
                    f"PublicKey = <SERVER_PUBKEY>\n"
                    f"Endpoint = {server_ip}:51820\n"
                    f"AllowedIPs = 0.0.0.0/0\n"
                )
            else:
                client_uuid = str(uuid.uuid4())
                user_email = f"user_{user_id}_{client_uuid[:8]}@safeflow"

                # Запрос к агенту
                async with httpx.AsyncClient() as client:
                    try:
                        resp = await client.post(
                            f"{agent_url}/xray",
                            json={"uuid": client_uuid, "email": user_email},
                            headers=headers,
                            timeout=5.0
                        )
                        if resp.status_code != 200:
                            raise ValueError(f"Agent error: {resp.text}")
                    except httpx.RequestError as e:
                        print(f"Failed to connect to agent: {e}")

                config_data = (
                    f"vless://{client_uuid}@{server_ip}:443"
                    f"?type=tcp&security=reality&sni=google.com#SafeFlow_Xray"
                )

            # Создаем ключ
            key = await self.uow.keys.create({
                "user_id": user_id,
                "server_id": server_id,
                "protocol": protocol,
                "internal_ip": internal_ip,
                "client_uuid": client_uuid,
                "config_data": config_data,
                "status": KeyStatus.ACTIVE
            })

            # Увеличиваем нагрузку на сервер
            current_load = getattr(server, "current_load", 0)
            await self.uow.servers.update(
                server, {"current_load": current_load + 1}
            )

            return KeyResponse.model_validate({
                "id": getattr(key, "id", 1),
                "user_id": user_id,
                "server_id": server_id,
                "protocol": protocol,
                "internal_ip": internal_ip,
                "client_uuid": client_uuid,
                "config_data": config_data,
                "status": KeyStatus.ACTIVE
            })
