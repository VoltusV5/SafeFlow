from cryptography.fernet import Fernet

def encrypt_data(data: str, key: str) -> str:
    """
    Encrypts string data using Fernet symmetric encryption.
    :param data: The plaintext string to encrypt.
    :param key: The URL-safe base64-encoded 32-byte key.
    :return: The encrypted string (URL-safe base64-encoded).
    """
    f = Fernet(key.encode('utf-8'))
    return f.encrypt(data.encode('utf-8')).decode('utf-8')


def decrypt_data(encrypted_data: str, key: str) -> str:
    """
    Decrypts string data using Fernet symmetric encryption.
    :param encrypted_data: The encrypted string.
    :param key: The URL-safe base64-encoded 32-byte key.
    :return: The decrypted plaintext string.
    """
    f = Fernet(key.encode('utf-8'))
    return f.decrypt(encrypted_data.encode('utf-8')).decode('utf-8')
