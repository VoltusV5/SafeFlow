"""Тесты для команд бота (Aiogram 3)."""

from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message, User

from app.bot.handlers.commands import command_start, command_help
from tests.services.mock_uow import MockUnitOfWork


@pytest.mark.asyncio
async def test_command_start():
    """Тест команды /start."""
    message = AsyncMock(spec=Message)
    message.text = "/start"
    message.answer = AsyncMock()
    
    # Мокаем from_user как объект User, чтобы user.id был доступен
    mock_user = User(id=12345, is_bot=False, first_name="Test")
    message.from_user = mock_user
    
    uow = MockUnitOfWork()
    
    await command_start(message=message, uow=uow)
    
    # Проверяем, что бота ответил
    message.answer.assert_called_once()
    _, kwargs = message.answer.call_args
    assert "Добро пожаловать" in kwargs.get("text", "")
    assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_command_help():
    """Тест команды /help."""
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    
    await command_help(message=message)
    
    message.answer.assert_called_once()
    _, kwargs = message.answer.call_args
    assert "Доступные команды" in kwargs.get("text", "")


@pytest.mark.asyncio
async def test_command_subscribe():
    from app.bot.handlers.commands import command_subscribe
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    
    await command_subscribe(message=message)
    
    message.answer.assert_called_once()
    _, kwargs = message.answer.call_args
    assert "Выберите тариф" in kwargs.get("text", "")
    assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_command_promo():
    from app.bot.handlers.commands import command_promo
    message = AsyncMock(spec=Message)
    message.answer = AsyncMock()
    
    await command_promo(message=message)
    
    message.answer.assert_called_once()
    _, kwargs = message.answer.call_args
    assert "Активация промокода" in kwargs.get("text", "")
