"""Mock Unit of Work для тестирования бизнес-логики.

Модуль определяет классы-заглушки для UoW и репозиториев, чтобы
тестировать сервисы без обращения к реальной базе данных.
"""

from typing import Any, Dict, List

from app.db.uow import UnitOfWork


class MockRepository:
    """Mock-репозиторий."""

    def __init__(self):
        self.data: Dict[Any, Any] = {}
        self.id_counter = 1

    async def get(self, id: Any) -> Any:
        return self.data.get(id)

    async def get_all(self) -> List[Any]:
        return list(self.data.values())

    async def create(self, obj_in: Dict[str, Any]) -> Any:
        # Псевдо-модель, которая ведет себя как объект
        class MockModel:
            def __init__(self, data):
                for k, v in data.items():
                    setattr(self, k, v)
                if not hasattr(self, "id"):
                    self.id = None
                if not hasattr(self, "balance"):
                    self.balance = 0
                if not hasattr(self, "is_banned"):
                    self.is_banned = False
                if not hasattr(self, "created_at"):
                    from datetime import datetime, timezone
                    self.created_at = datetime.now(timezone.utc)
                if not hasattr(self, "notification_preference"):
                    self.notification_preference = "telegram"

        obj = MockModel(obj_in)
        if obj.id is None:
            obj.id = self.id_counter
            self.id_counter += 1
        self.data[obj.id] = obj
        return obj

    async def update(self, db_obj: Any, obj_in: Dict[str, Any]) -> Any:
        for field, value in obj_in.items():
            setattr(db_obj, field, value)
        return db_obj

    async def delete(self, id: Any) -> bool:
        if id in self.data:
            del self.data[id]
            return True
        return False


class MockUserRepository(MockRepository):
    """Заглушка для репозитория пользователей."""

    async def get_by_tg_id(self, tg_id: int):
        for user in self.data.values():
            if getattr(user, "telegram_id", None) == tg_id or getattr(user, "tg_id", None) == tg_id:
                return user
        return None


class MockSubscriptionRepository(MockRepository):
    """Заглушка для репозитория подписок."""
    pass


class MockKeyRepository(MockRepository):
    async def get_occupied_ips(self):
        return [getattr(k, "ip_address") for k in self.data.values() if hasattr(k, "ip_address")]

    async def get_active_by_user_id(self, user_id):
        from app.core.enums import KeyStatus
        return [
            k for k in self.data.values()
            if getattr(k, "user_id", None) == user_id
            and getattr(k, "status", None) in (KeyStatus.ACTIVE, "active")
        ]

    async def get_by_user(self, user_id: int):
        return [k for k in self.data.values() if getattr(k, "user_id", None) == user_id]


class MockServerRepository(MockRepository):
    pass


class MockPromocodeRepository(MockRepository):
    async def get_by_code(self, code):
        for p in self.data.values():
            if getattr(p, "code", None) == code:
                return p
        return None


class MockPaymentRepository(MockRepository):
    pass


class MockRefundTicketRepository(MockRepository):
    pass


class MockUnitOfWork(UnitOfWork):
    """Заглушка для Unit of Work."""

    def __init__(self):
        self.users = MockUserRepository()
        self.subscriptions = MockSubscriptionRepository()
        self.keys = MockKeyRepository()
        self.servers = MockServerRepository()
        self.promocodes = MockPromocodeRepository()
        self.payments = MockPaymentRepository()
        self.refund_tickets = MockRefundTicketRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True
