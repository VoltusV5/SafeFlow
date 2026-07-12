"""Sandbox-роутер для имитации платёжной системы.

Позволяет тестировать полный цикл оплаты локально, без подключения
к реальному платёжному шлюзу. Включается только в режиме payment_mode=sandbox.

Эндпоинты:
    GET  /sandbox/checkout/{payment_id} — страница оплаты (нажми «Оплатить»)
    POST /sandbox/confirm/{payment_id}  — симулирует вебхук от платежной системы
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.api.dependencies import get_uow
from app.core.enums import PaymentStatus
from app.db.uow import UnitOfWork
from app.services.billing_service import BillingService
from app.services.payment_providers import SandboxProvider

router = APIRouter()

logger = logging.getLogger(__name__)


def _payment_page_html(payment_id: int, amount: int, error: str = "") -> str:
    """Генерирует HTML-страницу оплаты в стиле «банковского» экрана.

    Args:
        payment_id: ID платежа.
        amount: Сумма в копейках.
        error: Сообщение об ошибке (если есть).

    Returns:
        HTML-строка страницы.
    """
    amount_rub = amount / 100
    error_block = (
        f'<div class="error">{error}</div>' if error else ""
    )
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SafeFlow VPN — Оплата</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
  }}
  .card {{
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.12);
    backdrop-filter: blur(20px);
    border-radius: 24px;
    padding: 48px 40px;
    width: 100%; max-width: 420px;
    text-align: center;
    box-shadow: 0 24px 64px rgba(0,0,0,0.4);
  }}
  .badge {{
    display: inline-block;
    background: rgba(255,180,0,0.15);
    color: #ffd700;
    border: 1px solid rgba(255,215,0,0.3);
    border-radius: 8px; padding: 4px 12px;
    font-size: 12px; font-weight: 600;
    letter-spacing: 1px; margin-bottom: 24px;
  }}
  h1 {{ color: #fff; font-size: 22px; margin-bottom: 8px; }}
  .subtitle {{ color: rgba(255,255,255,0.5); font-size: 14px; margin-bottom: 32px; }}
  .amount {{
    background: rgba(100,200,100,0.1);
    border: 1px solid rgba(100,200,100,0.3);
    border-radius: 16px; padding: 20px;
    margin-bottom: 32px;
  }}
  .amount-label {{ color: rgba(255,255,255,0.5); font-size: 12px; margin-bottom: 4px; }}
  .amount-value {{ color: #7fff7f; font-size: 36px; font-weight: 700; }}
  .amount-currency {{ color: rgba(255,255,255,0.5); font-size: 16px; }}
  .order-id {{ color: rgba(255,255,255,0.4); font-size: 12px; margin-top: 8px; }}
  button {{
    width: 100%;
    background: linear-gradient(135deg, #00d2ff, #3a7bd5);
    color: #fff; border: none; border-radius: 14px;
    padding: 16px; font-size: 16px; font-weight: 600;
    cursor: pointer; transition: all 0.2s; margin-bottom: 12px;
  }}
  button:hover {{ transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,210,255,0.3); }}
  button:active {{ transform: translateY(0); }}
  .cancel {{
    color: rgba(255,255,255,0.4); font-size: 13px;
    background: none; padding: 8px; text-decoration: underline;
  }}
  .error {{
    background: rgba(255,80,80,0.1);
    border: 1px solid rgba(255,80,80,0.3);
    color: #ff8080; border-radius: 10px;
    padding: 12px; margin-bottom: 16px; font-size: 14px;
  }}
  .sandbox-note {{
    color: rgba(255,215,0,0.5); font-size: 11px;
    margin-top: 20px; line-height: 1.4;
  }}
</style>
</head>
<body>
<div class="card">
  <div class="badge">🧪 SANDBOX MODE</div>
  <h1>Оплата подписки SafeFlow VPN</h1>
  <p class="subtitle">Нажмите кнопку для подтверждения (тестовая оплата)</p>
  {error_block}
  <div class="amount">
    <div class="amount-label">К оплате</div>
    <div>
      <span class="amount-value">{amount_rub:.2f}</span>
      <span class="amount-currency"> ₽</span>
    </div>
    <div class="order-id">Заказ #{payment_id}</div>
  </div>
  <form method="post" action="/api/v1/payments/sandbox/confirm/{payment_id}">
    <button type="submit">✅ Оплатить (Sandbox)</button>
  </form>
  <p class="sandbox-note">
    ⚠️ Это тестовый режим. Реальные деньги не списываются.<br>
    Замените SandboxProvider на реальный шлюз перед запуском в прод.
  </p>
</div>
</body>
</html>"""


@router.get("/checkout/{payment_id}", response_class=HTMLResponse)
async def sandbox_checkout(
    payment_id: int,
    request: Request,
    uow: UnitOfWork = Depends(get_uow)
):
    """Страница оплаты в sandbox-режиме.

    Показывает красивую HTML-форму с информацией о платеже.
    Пользователь нажимает «Оплатить» → вызывается /confirm/{payment_id}.

    Args:
        payment_id: ID платежа в нашей системе.
        request: HTTP-запрос.
        uow: Unit of Work.
    """
    payment = await uow.payments.get(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Payment {payment_id} not found"
        )

    if payment.status != PaymentStatus.PENDING:
        return HTMLResponse(content=_payment_page_html(
            payment_id, 0,
            error="Этот платёж уже обработан или был отменён."
        ))

    amount = getattr(payment, "amount", 0)
    return HTMLResponse(content=_payment_page_html(payment_id, amount))


@router.post("/confirm/{payment_id}")
async def sandbox_confirm(
    payment_id: int,
    uow: UnitOfWork = Depends(get_uow)
):
    """Имитирует успешный вебхук от платёжной системы.

    В реальном проекте этот эндпоинт вызывает платёжная система.
    В sandbox — вызывается кнопкой на странице /checkout/{payment_id}.

    Args:
        payment_id: ID платежа.
        uow: Unit of Work.
    """
    payment = await uow.payments.get(payment_id)
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    if payment.status != PaymentStatus.PENDING:
        logger.info(f"[Sandbox] Payment {payment_id} already processed (status={payment.status})")
        return {"status": "already_processed", "payment_id": payment_id}

    billing_service = BillingService(uow)
    sub = await billing_service.complete_payment(payment_id)

    logger.info(
        f"[Sandbox] Payment {payment_id} completed. "
        f"User {payment.user_id} subscription active until {sub.expires_at}"
    )

    return {
        "status": "success",
        "payment_id": payment_id,
        "subscription": {
            "plan": sub.plan,
            "expires_at": sub.expires_at.isoformat(),
            "is_active": sub.is_active
        }
    }
