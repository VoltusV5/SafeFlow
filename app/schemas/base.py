"""Базовые схемы Pydantic.

Содержит базовую конфигурацию для всех DTO.
"""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Базовая схема для всех DTO.

    Включает поддержку преобразования из SQLAlchemy моделей.
    """

    model_config = ConfigDict(from_attributes=True)
