"""Схемы (DTO) для биллинга.

Модуль определяет структуры данных для подписок, платежей и промокодов.
"""

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.core.enums import (PaymentStatus, PaymentType, PlanType,
                            RefundTicketStatus)
from app.schemas.base import BaseSchema


class SubscriptionResponse(BaseSchema):
    """Схема ответа с данными подписки."""

    id: int
    user_id: int
    plan: PlanType
    expires_at: datetime
    base_device_limit: int
    is_active: bool


class PaymentCreate(BaseSchema):
    """Схема для создания платежа."""

    user_id: int
    amount: int = Field(gt=0)
    currency: str = "RUB"
    status: PaymentStatus = PaymentStatus.PENDING
    payment_type: PaymentType
    promocode: Optional[str] = None


class PaymentUpdate(BaseSchema):
    """Схема для обновления статуса платежа."""

    gateway_payment_id: Optional[str] = None
    status: PaymentStatus


class PaymentResponse(BaseSchema):
    """Схема ответа с данными платежа."""

    id: int
    user_id: int
    gateway_payment_id: Optional[str]
    amount: int
    currency: str
    status: PaymentStatus
    payment_type: PaymentType
    promocode: Optional[str]
    created_at: datetime


class PromocodeResponse(BaseSchema):
    """Схема ответа с данными промокода."""

    code: str
    discount_percent: int
    max_uses: Optional[int]
    used_count: int
    is_active: bool


class RefundTicketResponse(BaseSchema):
    """Схема ответа для заявки на возврат."""

    id: int
    user_id: int
    payment_id: int
    amount_calculated: int
    status: RefundTicketStatus
