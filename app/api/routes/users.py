"""Роутер для работы с профилем пользователя."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_uow
from app.db.models.user import User
from app.db.uow import UnitOfWork
from app.schemas.user import UserMeResponse, UserResponse, SubscriptionInfo

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_uow)
) -> dict:
    """Получает профиль текущего пользователя и его активную подписку."""
    
    # Формируем данные пользователя
    user_data = UserResponse(
        id=current_user.id,
        telegram_id=getattr(current_user, "tg_id", None) or getattr(current_user, "telegram_id", 0),
        username=current_user.username,
        balance=getattr(current_user, "balance", 0),
        is_banned=getattr(current_user, "is_banned", False),
        created_at=current_user.created_at
    )
    
    # Получаем активную подписку
    subs = await uow.subscriptions.get_all()
    active_sub = next(
        (s for s in subs if getattr(s, "user_id", None) == current_user.id and getattr(s, "is_active", False)),
        None
    )
    
    sub_info = None
    if active_sub:
        plan_val = getattr(active_sub, "plan", None)
        plan_str = plan_val.value if hasattr(plan_val, "value") else str(plan_val)
        sub_info = SubscriptionInfo(
            plan=plan_str,
            expires_at=getattr(active_sub, "expires_at", None),
            is_active=True
        )
        
    return {
        "user": user_data,
        "active_subscription": sub_info
    }
