"""Схемы (DTO) для VPN.

Модуль определяет структуры данных для VPN ключей и серверов.
"""

from typing import Optional

from app.core.enums import Country, KeyStatus, Protocol
from app.schemas.base import BaseSchema


class ServerResponse(BaseSchema):
    """Схема ответа с данными сервера."""

    id: int
    name: str
    country: Country
    ip_address: str
    is_active: bool
    current_load: int
    max_capacity: int


class KeyCreate(BaseSchema):
    """Схема для создания VPN ключа."""

    user_id: int
    server_id: int
    protocol: Protocol
    internal_ip: Optional[str] = None
    client_uuid: Optional[str] = None
    config_data: str
    status: KeyStatus = KeyStatus.ACTIVE


class KeyResponse(BaseSchema):
    """Схема ответа с данными ключа."""

    id: int
    user_id: int
    server_id: int
    protocol: Protocol
    internal_ip: Optional[str]
    client_uuid: Optional[str]
    config_data: str
    status: KeyStatus
