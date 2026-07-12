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


def test_decrypt_invalid_token():
    """Тест обработки некорректных зашифрованных данных.

    Проверяет, что при попытке расшифровать мусорную строку
    срабатывает исключение.
    """
    test_key = Fernet.generate_key().decode("utf-8")
    with pytest.raises(Exception):
        decrypt_data("invalid_encrypted_string_that_is_garbage", test_key)
