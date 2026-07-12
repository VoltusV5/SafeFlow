"""Роутер для управления ключами VPN."""

from typing import List

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_uow
from app.db.models.user import User
from app.db.uow import UnitOfWork

from app.schemas.vpn import KeyResponse

router = APIRouter()


@router.get("/my", response_model=List[KeyResponse])
async def get_my_keys(
    current_user: User = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_uow)
) -> List[dict]:
    """Получает список ключей текущего пользователя."""
    # Получаем все ключи пользователя
    keys = await uow.keys.get_by_user(current_user.id)

    # Формируем ответ, используя Pydantic схему KeyResponse
    result = []
    for key in keys:
        result.append(KeyResponse.model_validate(key, from_attributes=True))

    return result
