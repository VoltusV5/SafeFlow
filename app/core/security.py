"""Утилиты безопасности и шифрования.

Модуль предоставляет функции для симметричного шифрования строк (например, конфигураций VPN).  # noqa: E501
"""

from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet
from passlib.context import CryptContext

from app.core.config import settings


def encrypt_data(data: str, key: str) -> str:
    """Шифрует данные с использованием Fernet и предоставленного ключа.

    Args:
        data (str): Исходные данные для шифрования.
        key (str): Ключ шифрования в формате Fernet.

    Returns:
        str: Зашифрованные данные в виде строки (URL-safe base64).
    """
    f = Fernet(key.encode("utf-8"))
    return f.encrypt(data.encode("utf-8")).decode("utf-8")


def decrypt_data(encrypted_data: str, key: str) -> str:
    """Расшифровывает строковые данные, зашифрованные через Fernet.

    Args:
        encrypted_data: Зашифрованная строка.
        key: Ключ шифрования (URL-safe base64-кодированный 32-байтный ключ).

    Returns:
        Расшифрованная (исходная) строка.
    """
    f = Fernet(key.encode("utf-8"))
    return f.decrypt(encrypted_data.encode("utf-8")).decode("utf-8")


def create_access_token(
    data: dict, expires_delta: timedelta | None = None
) -> str:
    """Создает JWT токен доступа.

    Args:
        data: Данные (payload) для включения в токен.
        expires_delta: Необязательное время жизни токена. 
            Если не указано, берется из настроек.

    Returns:
        Сгенерированный JWT токен.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def verify_access_token(token: str) -> dict | None:
    """Проверяет JWT токен и возвращает payload, если он валиден.

    Args:
        token: JWT токен для проверки.

    Returns:
        Словарь (payload) токена, или None, если токен невалиден/истек.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.PyJWTError:
        return None


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие пароля хэшу."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Генерирует хэш пароля."""
    return pwd_context.hash(password)
