"""Модель VPN-ключа базы данных.

Модуль определяет класс Key для хранения конфигураций VPN подключений.
"""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class Key(Base):
    """Модель VPN-ключа пользователя.

    Хранит сгенерированные конфигурации, привязку к серверу и протоколу.

    Attributes:
        id: Внутренний идентификатор ключа.
        user_id: Идентификатор владельца ключа.
        server_id: Идентификатор сервера, на котором выпущен ключ.
        protocol: Протокол подключения (например, Vless, WG).
        internal_ip: Внутренний IP-адрес ключа в виртуальной сети (может быть None).  # noqa: E501
        client_uuid: Уникальный UUID клиента для протоколов Xray/Vless (может быть None).  # noqa: E501
        config_data: Содержимое конфигурации (в зашифрованном или открытом виде).  # noqa: E501
        status: Текущий статус ключа (например, active, suspended).
        user: Пользователь-владелец.
        server: Сервер, на котором находится ключ.
    """

    __tablename__ = "keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    server_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servers.id"), nullable=False
    )
    protocol: Mapped[str] = mapped_column(String, nullable=False)
    internal_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    config_data: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")

    # relationships
    user = relationship("User", back_populates="keys")
    server = relationship("Server", back_populates="keys")
