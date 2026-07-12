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
from app.schemas.user import UserCreate, UserEmailLogin, RegisterInitRequest, RegisterConfirmRequest, LoginCodeInitRequest, LoginCodeConfirmRequest
from app.services.user_service import UserService
from app.services.email_service import send_otp_email
from app.core.redis import get_redis

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
@limiter.limit("5/minute")
async def auth_login_basic(
    request: Request,
    payload: UserEmailLogin,
    uow: UnitOfWork = Depends(get_uow)
):
    """Классическая авторизация по email и паролю."""
    from app.core.security import verify_password
    
    async with uow:
        user = await uow.users.get_by_email(payload.email)
        if not user or not user.hashed_password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        if not verify_password(payload.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token = create_access_token(data={"sub": str(user.id)})
        return {"access_token": access_token, "token_type": "bearer"}


import secrets
import logging

logger = logging.getLogger(__name__)

@router.post("/register-init")
@limiter.limit("3/minute")
async def auth_register_init(
    request: Request,
    payload: RegisterInitRequest,
    uow: UnitOfWork = Depends(get_uow)
):
    """Инициализация регистрации: сохраняет данные, отправляет код."""
    async with uow:
        existing = await uow.users.get_by_email(payload.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

    redis_client = await get_redis()
    
    # Генерация 6-значного кода
    code = f"{secrets.randbelow(1000000):06d}"
    
    # Сохраняем в Redis на 10 минут
    data = {"password": payload.password, "code": code}
    await redis_client.setex(f"reg_otp:{payload.email}", 600, json.dumps(data))
    
    # Пока что выводим в консоль
    logger.info(f"MOCK EMAIL CODE for REGISTRATION ({payload.email}): {code}")
    
    return {"message": "Registration code sent to email"}


@router.post("/register-confirm")
async def auth_register_confirm(
    payload: RegisterConfirmRequest,
    uow: UnitOfWork = Depends(get_uow)
):
    """Подтверждение регистрации по коду."""
    redis_client = await get_redis()
    key = f"reg_otp:{payload.email}"
    
    saved_data_str = await redis_client.get(key)
    if not saved_data_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired registration code"
        )
        
    saved_data = json.loads(saved_data_str)
    
    if saved_data["code"] != payload.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code"
        )
        
    # Удаляем код
    await redis_client.delete(key)
    
    # Создаем пользователя
    user_service = UserService(uow)
    user_in = UserCreate(email=payload.email, password=saved_data["password"])
    
    try:
        user = await user_service.register_user(user_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id}


@router.post("/login-code-init")
@limiter.limit("3/minute")
async def auth_login_code_init(
    request: Request,
    payload: LoginCodeInitRequest,
    uow: UnitOfWork = Depends(get_uow)
):
    """Инициализация входа по коду: отправляет код на email."""
    async with uow:
        user = await uow.users.get_by_email(payload.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

    redis_client = await get_redis()
    
    code = f"{secrets.randbelow(1000000):06d}"
    await redis_client.setex(f"login_otp:{payload.email}", 300, code)
    
    # Пока что выводим в консоль
    logger.info(f"MOCK EMAIL CODE for LOGIN ({payload.email}): {code}")
    
    return {"message": "Login code sent to email"}


@router.post("/login-code-confirm")
async def auth_login_code_confirm(
    payload: LoginCodeConfirmRequest,
    uow: UnitOfWork = Depends(get_uow)
):
    """Подтверждение входа по коду."""
    redis_client = await get_redis()
    key = f"login_otp:{payload.email}"
    
    saved_code = await redis_client.get(key)
    if not saved_code or saved_code != payload.code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired login code"
        )
        
    await redis_client.delete(key)
    
    async with uow:
        user = await uow.users.get_by_email(payload.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


