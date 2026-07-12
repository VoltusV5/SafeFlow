"""Инициализация репозиториев базы данных.

Модуль предоставляет доступ ко всем классам репозиториев.
"""
from app.db.repositories.base import BaseRepository
from app.db.repositories.key import KeyRepository
from app.db.repositories.payment import PaymentRepository
from app.db.repositories.promocode import PromocodeRepository
from app.db.repositories.refund_ticket import RefundTicketRepository
from app.db.repositories.server import ServerRepository
from app.db.repositories.subscription import SubscriptionRepository
from app.db.repositories.user import UserRepository
