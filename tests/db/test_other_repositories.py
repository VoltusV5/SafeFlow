"""Тесты для дополнительных репозиториев.

Модуль содержит unit-тесты для ServerRepository, KeyRepository,
PaymentRepository, PromocodeRepository, RefundTicketRepository.
"""

import pytest

from app.core.enums import Country, Protocol
from app.db.repositories.key import KeyRepository
from app.db.repositories.payment import PaymentRepository
from app.db.repositories.promocode import PromocodeRepository
from app.db.repositories.refund_ticket import RefundTicketRepository
from app.db.repositories.server import ServerRepository
from app.db.repositories.user import UserRepository


@pytest.mark.asyncio
async def test_server_repository(async_session):
    """Тест ServerRepository.

    Проверяет получение списка активных серверов.
    """
    repo = ServerRepository(async_session)
    await repo.create(
        {
            "country": Country.POLAND,
            "domain": "pl.example.com",
            "api_secret": "sec",
            "is_active": True,
        }
    )
    await repo.create(
        {
            "country": Country.USA,
            "domain": "us.example.com",
            "api_secret": "sec",
            "is_active": False,
        }
    )

    active = await repo.get_active_servers()
    assert len(active) == 1
    assert active[0].country == Country.POLAND


@pytest.mark.asyncio
async def test_key_repository(async_session):
    """Тест KeyRepository.

    Проверяет получение ключей пользователя.
    """
    user_repo = UserRepository(async_session)
    server_repo = ServerRepository(async_session)
    key_repo = KeyRepository(async_session)

    user = await user_repo.create({"tg_id": 222, "username": "u"})
    server = await server_repo.create(
        {"country": Country.POLAND, "domain": "d", "api_secret": "s"}
    )

    await key_repo.create(
        {
            "user_id": user.id,
            "server_id": server.id,
            "protocol": Protocol.AWG,
            "config_data": "data",
        }
    )

    keys = await key_repo.get_by_user_id(user.id)
    assert len(keys) == 1


@pytest.mark.asyncio
async def test_payment_repository(async_session):
    """Тест PaymentRepository.

    Проверяет получение истории платежей пользователя.
    """
    user_repo = UserRepository(async_session)
    pay_repo = PaymentRepository(async_session)

    user = await user_repo.create({"tg_id": 333, "username": "u"})
    await pay_repo.create(
        {
            "user_id": user.id,
            "amount": 10000,
            "status": "success",
            "payment_type": "card",
        }
    )

    payments = await pay_repo.get_by_user_id(user.id)
    assert len(payments) == 1


@pytest.mark.asyncio
async def test_promocode_repository(async_session):
    """Тест PromocodeRepository.

    Проверяет получение промокода по его значению.
    """
    repo = PromocodeRepository(async_session)
    await repo.create({"code": "TEST50", "discount_pct": 50, "max_uses": 100})

    promo = await repo.get_by_code("TEST50")
    assert promo is not None
    assert promo.discount_pct == 50


@pytest.mark.asyncio
async def test_refund_ticket_repository(async_session):
    """Тест RefundTicketRepository.

    Проверяет получение заявок на возврат по пользователю.
    """
    user_repo = UserRepository(async_session)
    pay_repo = PaymentRepository(async_session)
    refund_repo = RefundTicketRepository(async_session)

    user = await user_repo.create({"tg_id": 444, "username": "u"})
    payment = await pay_repo.create(
        {
            "user_id": user.id,
            "amount": 10000,
            "status": "success",
            "payment_type": "card",
        }
    )

    await refund_repo.create(
        {
            "user_id": user.id,
            "payment_id": payment.id,
            "amount_calculated": 5000,
            "status": "pending",
        }
    )

    tickets = await refund_repo.get_by_user_id(user.id)
    assert len(tickets) == 1
