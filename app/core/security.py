"""Утилиты безопасности и шифрования.

Модуль предоставляет функции для симметричного шифрования строк (например, конфигураций VPN).  # noqa: E501
"""

from cryptography.fernet import Fernet


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
