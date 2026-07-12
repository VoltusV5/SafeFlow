"""Роутер для обработки платежей и вебхуков."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies import get_uow
from app.core.config import settings
from app.core.enums import PaymentStatus
from app.db.uow import UnitOfWork
from app.services.billing_service import BillingService
from app.services.payment_providers import (AAIOProvider, BasePaymentProvider,
                                            get_payment_provider)

router = APIRouter()
logger = logging.getLogger(__name__)


async def process_webhook(provider: BasePaymentProvider, request: Request, uow: UnitOfWork):
    """Общая логика обработки вебхука от платежного провайдера.

    1. Проверка подписи.
    2. Извлечение ID платежа.
    3. Активация подписки через BillingService.

    Args:
        provider: Провайдер платёжной системы.
        request: HTTP-запрос.
        uow: Unit of Work.
    """
    form_data = await request.form()
    data_dict = dict(form_data)

    if not await provider.verify_signature(request, data_dict):
        logger.warning("Invalid webhook signature from %s", request.client)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    order_id = provider.extract_order_id(data_dict)
    if not order_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid order_id"
        )

    payment = await uow.payments.get(order_id)
    if not payment:
        logger.warning("Payment %s not found in webhook", order_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    if payment.status != PaymentStatus.PENDING:
        # Идемпотентность: платёж уже обработан — просто отвечаем OK
        return "OK"

    billing_service = BillingService(uow)
    await billing_service.complete_payment(payment.id)

    return "OK"


@router.post("/aaio/webhook")
async def aaio_webhook(request: Request, uow: UnitOfWork = Depends(get_uow)):
    """Вебхук от платёжной системы AAIO (только для production-режима)."""
    if settings.payment_mode != "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AAIO webhook disabled in sandbox mode"
        )
    provider = AAIOProvider()
    return await process_webhook(provider, request, uow)
