"""Инициализация моделей базы данных.

Модуль собирает все SQLAlchemy модели в одном месте для Alembic и приложения.
"""

from app.db.models.base import Base
from app.db.models.user import User
from app.db.models.subscription import Subscription
from app.db.models.payment import Payment
from app.db.models.key import Key
from app.db.models.server import Server
from app.db.models.promocode import Promocode
from app.db.models.refund_ticket import RefundTicket

__all__ = [
    "Base",
    "User",
    "Subscription",
    "Payment",
    "Key",
    "Server",
    "Promocode",
    "RefundTicket",
]
