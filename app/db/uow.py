"""Паттерн Unit of Work для управления транзакциями.

Модуль определяет класс UnitOfWork, который инкапсулирует
инициализацию репозиториев и обеспечивает атомарность бизнес-операций.
"""

from typing import Any, Callable, Coroutine, Type

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.key import KeyRepository
from app.db.repositories.payment import PaymentRepository
from app.db.repositories.promocode import PromocodeRepository
from app.db.repositories.refund_ticket import RefundTicketRepository
from app.db.repositories.server import ServerRepository
from app.db.repositories.subscription import SubscriptionRepository
from app.db.repositories.user import UserRepository
from app.db.session import AsyncSessionLocal


class UnitOfWork:
    """Класс Unit of Work.

    Управляет транзакцией базы данных и предоставляет доступ к репозиториям.
    """

    def __init__(self) -> None:
        """Инициализация Unit of Work.

        Создает фабрику сессий. Сама сессия создается при входе в контекстный менеджер.
        """
        self.session_factory = AsyncSessionLocal
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "UnitOfWork":
        """Вход в контекстный менеджер.

        Создает новую сессию БД и инициализирует все репозитории.

        Returns:
            Объект UnitOfWork с инициализированными репозиториями.
        """
        self.session = self.session_factory()

        # Инициализация репозиториев
        self.users = UserRepository(self.session)
        self.keys = KeyRepository(self.session)
        self.payments = PaymentRepository(self.session)
        self.promocodes = PromocodeRepository(self.session)
        self.refund_tickets = RefundTicketRepository(self.session)
        self.servers = ServerRepository(self.session)
        self.subscriptions = SubscriptionRepository(self.session)

        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """Выход из контекстного менеджера.

        Выполняет commit() при отсутствии исключений, либо rollback() при ошибке,
        и закрывает сессию.

        Args:
            exc_type: Тип исключения (если возникло).
            exc_val: Значение исключения.
            exc_tb: Трассировка исключения.
        """
        if self.session is None:
            return

        try:
            if exc_type is not None:
                await self.session.rollback()
            else:
                await self.session.commit()
        finally:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        """Ручной коммит транзакции.

        Обычно не используется напрямую, так как коммит происходит
        автоматически при выходе из контекстного менеджера (__aexit__).
        """
        if self.session:
            await self.session.commit()

    async def rollback(self) -> None:
        """Ручной откат транзакции."""
        if self.session:
            await self.session.rollback()
