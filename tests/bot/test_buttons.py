"""Тесты для хендлеров кнопок бота (CallbackQuery)."""

from unittest.mock import AsyncMock

import pytest
from aiogram.types import CallbackQuery, Message, User

from app.bot.handlers.buttons import handle_profile, handle_keys, handle_tariffs
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_handle_profile():
    """Тест кнопки профиля."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "profile"
    callback.answer = AsyncMock()
    
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    callback.message = message
    
    mock_user = User(id=12345, is_bot=False, first_name="Test")
    callback.from_user = mock_user
    
    uow = MockUnitOfWork()
    
    # Сначала создаем юзера
    await uow.users.create({"tg_id": 12345, "balance": 100})
    
    await handle_profile(callback=callback, uow=uow)
    
    callback.answer.assert_called_once()
    message.answer.assert_called_once()
    
    _, kwargs = message.answer.call_args
    text = kwargs.get("text", "")
    assert "Ваш профиль" in text
    assert "100" in text


@pytest.mark.asyncio
async def test_handle_keys():
    """Тест кнопки Мои ключи."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "keys"
    callback.answer = AsyncMock()
    
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    callback.message = message
    
    mock_user = User(id=12345, is_bot=False, first_name="Test")
    callback.from_user = mock_user
    
    uow = MockUnitOfWork()
    user = await uow.users.create({"tg_id": 12345})
    
    from app.core.enums import KeyStatus
    await uow.keys.create({"user_id": user.id, "key_data": "vpn://test", "server_id": 1, "status": KeyStatus.ACTIVE})
    
    await handle_keys(callback=callback, uow=uow)
    
    callback.answer.assert_called_once()
    message.answer.assert_called_once()
    
    _, kwargs = message.answer.call_args
    assert "Ваши ключи" in kwargs.get("text", "")
    assert "vpn://test" in kwargs.get("text", "")


@pytest.mark.asyncio
async def test_handle_tariffs():
    """Тест кнопки Тарифы."""
    callback = AsyncMock(spec=CallbackQuery)
    callback.data = "tariffs"
    callback.answer = AsyncMock()
    
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    callback.message = message
    
    await handle_tariffs(callback=callback)
    
    callback.answer.assert_called_once()
    message.answer.assert_called_once()
    
    _, kwargs = message.answer.call_args
    assert "Выберите тариф" in kwargs.get("text", "")
    assert "reply_markup" in kwargs
