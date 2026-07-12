"""Интерфейс для работы с удаленными VPN серверами (Smart Agents).

Временно содержит заглушки, которые будут заменены на реальные HTTP-вызовы
в 10-м этапе разработки.
"""

import logging
from typing import Any, Dict


class VPNClientService:
    """Клиент для общения со Smart Agent на VPN нодах."""

    async def delete_key(self, server_ip: str, client_uuid_or_ip: str) -> bool:
        """Удаляет ключ с удаленного сервера.

        Args:
            server_ip: IP-адрес сервера (где запущен Smart Agent).
            client_uuid_or_ip: UUID клиента (Xray) или внутренний IP (AWG).

        Returns:
            True, если ключ успешно удален.
        """
        logging.info(
            f"[MOCK VPN] Deleting key {client_uuid_or_ip} on server {server_ip}")
        return True

    async def create_key(self, server_ip: str, config_data: Dict[str, Any]) -> bool:
        """Создает ключ на удаленном сервере.

        Args:
            server_ip: IP-адрес сервера.
            config_data: Конфигурация ключа.

        Returns:
            True, если ключ успешно создан.
        """
        logging.info(f"[MOCK VPN] Creating key on server {server_ip}: {config_data}")
        return True

    async def sync_key(
            self,
            server_ip: str,
            client_uuid_or_ip: str,
            expected_state: str) -> bool:
        """Синхронизирует состояние ключа (Reconciliation).

        Args:
            server_ip: IP-адрес сервера.
            client_uuid_or_ip: Идентификатор клиента.
            expected_state: Ожидаемое состояние ("active", "revoked" и т.д.).

        Returns:
            True, если синхронизация прошла успешно.
        """
        logging.info(
            f"[MOCK VPN] Syncing key {client_uuid_or_ip} "
            f"on {server_ip} to {expected_state}"
        )
        return True
