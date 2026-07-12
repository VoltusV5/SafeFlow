"""Пакет схем Pydantic (DTO)."""

from app.schemas.base import BaseSchema
from app.schemas.billing import (PaymentCreate, PaymentResponse, PaymentUpdate,
                                 PromocodeResponse, RefundTicketResponse,
                                 SubscriptionResponse)
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.schemas.vpn import KeyCreate, KeyResponse, ServerResponse

__all__ = [
    "BaseSchema",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "SubscriptionResponse",
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentResponse",
    "PromocodeResponse",
    "RefundTicketResponse",
    "ServerResponse",
    "KeyCreate",
    "KeyResponse",
]
