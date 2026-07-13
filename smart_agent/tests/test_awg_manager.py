import pytest
import os
import tempfile
from services.awg_manager import AWGManager
from schemas.keys import AWGKeyCreate


@pytest.fixture
def temp_config():
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, 'w') as f:
        f.write("[Interface]\nPrivateKey = test_priv\nListenPort = 51820\n")
    yield path
    os.remove(path)


def test_add_peer(temp_config):
    manager = AWGManager(config_path=temp_config)

    # Mock subprocess.run to prevent actual wg commands
    import subprocess
    original_run = subprocess.run
    subprocess.run = lambda *args, **kwargs: None

    try:
        peer = AWGKeyCreate(public_key="test_pub", preshared_key="test_psk", allowed_ip="10.8.0.2/32")
        result = manager.add_peer(peer)
        assert result is True

        with open(temp_config, "r") as f:
            content = f.read()
            assert "[Peer]" in content
            assert "PublicKey = test_pub" in content
            assert "AllowedIPs = 10.8.0.2/32" in content
            assert "PresharedKey = test_psk" in content

        # Try adding again
        result = manager.add_peer(peer)
        assert result is False
    finally:
        subprocess.run = original_run


def test_remove_peer(temp_config):
    manager = AWGManager(config_path=temp_config)
    import subprocess
    original_run = subprocess.run
    subprocess.run = lambda *args, **kwargs: None

    try:
        peer = AWGKeyCreate(public_key="test_pub", allowed_ip="10.8.0.2/32")
        manager.add_peer(peer)

        # Remove it
        result = manager.remove_peer("test_pub")
        assert result is True

        with open(temp_config, "r") as f:
            content = f.read()
            assert "PublicKey = test_pub" not in content

        # Remove non-existent
        result = manager.remove_peer("non_existent")
        assert result is False
    finally:
        subprocess.run = original_run
