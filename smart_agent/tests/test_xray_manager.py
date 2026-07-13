import pytest
from services.xray_manager import XrayManager
from schemas.keys import XrayKeyCreate


def test_add_client(monkeypatch):
    manager = XrayManager()

    # Mock subprocess.run
    def mock_run(*args, **kwargs):
        class Result:
            stdout = "success"
        return Result()

    monkeypatch.setattr("subprocess.run", mock_run)

    client = XrayKeyCreate(uuid="1234", email="test@test.com")
    assert manager.add_client(client) is True


def test_remove_client(monkeypatch):
    manager = XrayManager()

    def mock_run(*args, **kwargs):
        class Result:
            stdout = "success"
        return Result()

    monkeypatch.setattr("subprocess.run", mock_run)

    assert manager.remove_client("test@test.com") is True
