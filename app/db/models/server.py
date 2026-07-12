"""Модель сервера базы данных.

Модуль определяет класс Server для управления узлами (нодами) VPN.
"""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class Server(Base):
    """Модель VPN сервера.

    Содержит данные для подключения к агенту на сервере и его локацию.

    Attributes:
        id: Внутренний идентификатор сервера.
        country: Страна размещения сервера.
        domain: Доменное имя или IP адрес сервера.
        api_secret: Секретный ключ для авторизации запросов к агенту на сервере.  # noqa: E501
        is_active: Флаг доступности сервера для новых подключений.
        keys: Список ключей, выпущенных на данном сервере.
    """

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    country: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False)
    api_secret: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # relationships
    keys = relationship("Key", back_populates="server")
