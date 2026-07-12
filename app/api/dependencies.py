"""Зависимости (Dependencies) для FastAPI.

Модуль предоставляет функции, которые можно внедрять в роуты через Depends().
"""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import verify_access_token
from app.db.models.user import User
from app.db.uow import UnitOfWork

# OAuth2 схема, извлекающая токен из заголовка Authorization: Bearer ...
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    """Возвращает инициализированный UnitOfWork.

    Использует контекстный менеджер для гарантии закрытия сессии.
    """
    async with UnitOfWork() as uow:
        yield uow


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    uow: UnitOfWork = Depends(get_uow),
) -> User:
    """Извлекает текущего пользователя из токена.

    Args:
        token: JWT токен.
        uow: Unit of Work.

    Returns:
        User: Объект пользователя из базы данных.

    Raises:
        HTTPException: Если токен невалиден или пользователь не найден.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = verify_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    user = await uow.users.get(user_id)
    if user is None:
        raise credentials_exception

    if getattr(user, "is_banned", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is banned"
        )

    return user
