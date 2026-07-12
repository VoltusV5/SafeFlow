"""Тесты для менеджера VPN (VpnManagerService)."""

import pytest

from app.core.enums import Country, KeyStatus, Protocol
from app.services.vpn_manager import VpnManagerService
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_allocate_ip_success():
    """Тест успешной аллокации свободного IP адреса."""
    uow = MockUnitOfWork()
    service = VpnManagerService(uow)

    server = await uow.servers.create({
        "name": "NL-1",
        "country": Country.POLAND,
        "ip_address": "1.1.1.1",
        "is_active": True,
        "current_load": 0,
        "max_capacity": 100
    })

    await uow.keys.create({
        "server_id": server.id,
        "internal_ip": "10.8.0.2",
        "protocol": Protocol.AWG
    })
    await uow.keys.create({
        "server_id": server.id,
        "internal_ip": "10.8.0.3",
        "protocol": Protocol.AWG
    })

    new_ip = await service.allocate_ip(server.id)

    assert new_ip == "10.8.0.4"


@pytest.mark.asyncio
async def test_allocate_ip_skips_gateway():
    """Тест: адрес шлюза 10.8.0.1 не выдаётся клиентам."""
    uow = MockUnitOfWork()
    service = VpnManagerService(uow)

    server = await uow.servers.create({
        "name": "NL-1",
        "country": Country.POLAND,
        "ip_address": "1.1.1.1",
        "is_active": True,
        "current_load": 0,
        "max_capacity": 100
    })

    # Не добавляем никаких ключей — первый свободный должен быть .2, не .1
    new_ip = await service.allocate_ip(server.id)

    assert new_ip == "10.8.0.2"
    assert new_ip != "10.8.0.1"


@pytest.mark.asyncio
async def test_allocate_ip_no_free_addresses():
    """Тест: RuntimeError если нет свободных IP (все адреса заняты)."""
    uow = MockUnitOfWork()
    service = VpnManagerService(uow)

    server = await uow.servers.create({
        "name": "NL-1",
        "country": Country.POLAND,
        "ip_address": "1.1.1.1",
        "is_active": True,
        "current_load": 0,
        "max_capacity": 254
    })

    # Занимаем все 254 адреса подсети (10.8.0.2 — 10.8.0.254 + .255 broadcast)
    # Для теста заблокируем 10.8.0.2 — 10.8.0.254 (253 хоста)
    for i in range(2, 255):
        await uow.keys.create({
            "server_id": server.id,
            "internal_ip": f"10.8.0.{i}",
            "protocol": Protocol.AWG
        })

    with pytest.raises(RuntimeError, match="Нет свободных IP"):
        await service.allocate_ip(server.id)


@pytest.mark.asyncio
async def test_create_key():
    """Тест создания ключа VPN."""
    uow = MockUnitOfWork()
    service = VpnManagerService(uow)

    user = await uow.users.create({"telegram_id": 123})
    server = await uow.servers.create({
        "name": "NL-1",
        "country": Country.POLAND,
        "ip_address": "1.1.1.1",
        "is_active": True,
        "current_load": 0,
        "max_capacity": 100
    })

    key = await service.create_key(user.id, server.id, Protocol.AWG)

    assert key.internal_ip == "10.8.0.2"
    assert key.protocol == Protocol.AWG
    assert key.status == KeyStatus.ACTIVE
    assert uow.committed is True

    updated_server = await uow.servers.get(server.id)
    assert updated_server.current_load == 1


@pytest.mark.asyncio
async def test_create_key_xray_protocol():
    """Тест создания ключа с протоколом Xray (UUID вместо IP)."""
    uow = MockUnitOfWork()
    service = VpnManagerService(uow)

    user = await uow.users.create({"telegram_id": 456})
    server = await uow.servers.create({
        "name": "SE-1",
        "country": Country.SWEDEN,
        "ip_address": "2.2.2.2",
        "is_active": True,
        "current_load": 0,
        "max_capacity": 100
    })

    key = await service.create_key(user.id, server.id, Protocol.XRAY)

    assert key.protocol == Protocol.XRAY
    assert key.client_uuid is not None
    assert key.internal_ip is None
    assert key.status == KeyStatus.ACTIVE


@pytest.mark.asyncio
async def test_create_key_server_not_found():
    """Тест: ValueError если сервер не существует."""
    uow = MockUnitOfWork()
    service = VpnManagerService(uow)

    user = await uow.users.create({"telegram_id": 789})

    with pytest.raises(ValueError, match="Сервер не найден"):
        await service.create_key(user.id, 9999, Protocol.AWG)
