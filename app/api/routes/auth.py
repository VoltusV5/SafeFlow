"""Роутер авторизации.

Обеспечивает вход через Telegram и базовый вход по email/паролю.
"""

import hashlib
import hmac
import json
import time
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.api.dependencies import get_uow
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.uow import UnitOfWork
from app.schemas.user import UserCreate
from app.services.user_service import UserService

router = APIRouter()


class TelegramAuthRequest(BaseModel):
    """Схема запроса для авторизации через Telegram."""
    initData: str


def verify_telegram_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400
) -> dict | None:
    """Проверяет подпись initData от Telegram и возвращает данные пользователя.

    Args:
        init_data: Строка initData от Telegram Web App.
        bot_token: Токен Telegram-бота.
        max_age_seconds: Максимальный возраст данных в секундах (по умолчанию 24ч).

    Returns:
        Словарь с данными пользователя или None, если данные невалидны/устарели.
    """
    import time

    parsed_data = urllib.parse.parse_qsl(init_data)
    data_dict = dict(parsed_data)

    if "hash" not in data_dict:
        return None

    received_hash = data_dict.pop("hash")

    # Проверяем возраст данных (защита от replay-атак)
    auth_date_str = data_dict.get("auth_date")
    if auth_date_str:
        try:
            auth_date = int(auth_date_str)
            if time.time() - auth_date > max_age_seconds:
                return None
        except (ValueError, TypeError):
            return None

    sorted_keys = sorted(data_dict.keys())
    data_check_string = "\n".join(f"{k}={data_dict[k]}" for k in sorted_keys)

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    try:
        user_data = json.loads(data_dict.get("user", "{}"))
        return user_data
    except json.JSONDecodeError:
        return None


@router.post("/telegram")
@limiter.limit("10/minute")
async def auth_telegram(
    request: Request,
    payload: TelegramAuthRequest,
    uow: UnitOfWork = Depends(get_uow)
):
    """Авторизация пользователя через Telegram Web App.

    Ожидает initData от TWA, проверяет его и возвращает JWT токен.
    Лимит: 10 запросов в минуту с одного IP.
    """
    user_data = verify_telegram_data(payload.initData, settings.bot_token.get_secret_value())

    if not user_data or "id" not in user_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid initData"
        )

    # Ищем или создаём пользователя
    user_service = UserService(uow)
    user_in = UserCreate(
        telegram_id=user_data["id"],
        username=user_data.get("username")
    )
    user = await user_service.register_user(user_in)

    access_token = create_access_token(data={"sub": str(user.id)})

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login")
async def auth_login_basic(
    form_data: OAuth2PasswordRequestForm = Depends(),
    uow: UnitOfWork = Depends(get_uow)
):
    """Классическая авторизация по email и паролю."""
    # Заглушка, т.к. регистрация по email еще не реализована
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={"WWW-Authenticate": "Bearer"},
    )
