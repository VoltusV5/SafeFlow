import pytest
from cryptography.fernet import Fernet
from app.core.security import encrypt_data, decrypt_data

def test_encrypt_decrypt_data():
    """Test that data is properly encrypted and can be decrypted back to original."""
    original_text = "my_super_secret_config_data"
    test_key = Fernet.generate_key().decode('utf-8')
    
    encrypted = encrypt_data(original_text, test_key)
    
    # Verify the encrypted string is not the original string
    assert encrypted != original_text
    assert isinstance(encrypted, str)
    
    # Decrypt and verify it matches the original text
    decrypted = decrypt_data(encrypted, test_key)
    assert decrypted == original_text

def test_decrypt_invalid_token():
    """Test that trying to decrypt garbage throws an exception."""
    test_key = Fernet.generate_key().decode('utf-8')
    with pytest.raises(Exception):
        decrypt_data("invalid_encrypted_string_that_is_garbage", test_key)
