"""Тесты для модуля безопасности.

Модуль содержит unit-тесты для функций симметричного шифрования Fernet.
"""

import pytest
from cryptography.fernet import Fernet

from app.core.security import decrypt_data, encrypt_data


def test_encrypt_decrypt_data():
    """Тест успешного шифрования и расшифровки данных.

    Проверяет, что зашифрованная строка отличается от оригинала
    и успешно расшифровывается обратно.
    """
    original_text = "my_super_secret_config_data"
    test_key = Fernet.generate_key().decode("utf-8")

    encrypted = encrypt_data(original_text, test_key)

    # Verify the encrypted string is not the original string
    assert encrypted != original_text
    assert isinstance(encrypted, str)

    # Decrypt and verify it matches the original text
    decrypted = decrypt_data(encrypted, test_key)
    assert decrypted == original_text


# --- JWT Tests ---

def test_create_access_token():
    """Тест создания JWT токена."""
    # Assuming create_access_token exists in app.core.security
    import jwt

    from app.core.config import settings
    from app.core.security import create_access_token

    data = {"sub": "123"}
    token = create_access_token(data)

    # Verify token
    payload = jwt.decode(token, settings.jwt_secret.get_secret_value(),
                         algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == "123"
    assert "exp" in payload


def test_verify_access_token_valid():
    """Тест успешной верификации токена."""
    from app.core.security import create_access_token, verify_access_token
    data = {"sub": "user_id_456"}
    token = create_access_token(data)

    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user_id_456"


def test_verify_access_token_expired():
    """Тест верификации истекшего токена."""
    from datetime import timedelta

    from app.core.security import create_access_token, verify_access_token

    data = {"sub": "user_id_789"}
    # Token expires immediately
    token = create_access_token(data, expires_delta=timedelta(seconds=-1))

    payload = verify_access_token(token)
    assert payload is None


def test_decrypt_invalid_token():
    """Тест обработки некорректных зашифрованных данных.

    Проверяет, что при попытке расшифровать мусорную строку
    срабатывает исключение.
    """
    test_key = Fernet.generate_key().decode("utf-8")
    with pytest.raises(Exception):
        decrypt_data("invalid_encrypted_string_that_is_garbage", test_key)
