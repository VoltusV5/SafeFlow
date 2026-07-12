"""Конфигурация приложения.

Модуль для управления настройками приложения через переменные окружения (.env).
"""

from typing import List

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Класс настроек приложения.

    Загружает конфигурацию из файла .env и переменных окружения.

    Attributes:
        bot_token: Секретный токен Telegram бота.
        admin_ids: Список Telegram ID администраторов.
        postgres_user: Имя пользователя PostgreSQL.
        postgres_password: Пароль пользователя PostgreSQL.
        postgres_db: Название базы данных PostgreSQL.
        postgres_host: Хост базы данных.
        postgres_port: Порт базы данных.
        redis_host: Хост Redis.
        redis_port: Порт Redis.
        redis_db: Индекс базы данных Redis.
        fernet_key: Ключ симметричного шифрования Fernet.
        jwt_secret: Обязательный секрет для подписи JWT токенов.
        payment_mode: Режим оплаты ("sandbox" или "production").
    """

    # Telegram
    bot_token: SecretStr
    admin_ids: List[int] = []

    # Database (PostgreSQL)
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "safeflow"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """Генерирует строку подключения к PostgreSQL для asyncpg.

        Returns:
            Строка подключения SQLAlchemy.
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        """Генерирует строку подключения к Redis.

        Returns:
            Строка URL для подключения к Redis.
        """
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Security
    fernet_key: SecretStr

    # JWT Settings
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Payment
    # Режим платёжного провайдера: "sandbox" — локальная имитация, "production" — реальный шлюз
    payment_mode: str = "sandbox"

    # Payment Webhooks (AAIO) — нужны только в production режиме
    aaio_shop_id: str = "MOCK_SHOP_ID"
    aaio_secret_key: SecretStr = "MOCK_SECRET_KEY"  # Secret key #1 for signatures

    @field_validator("payment_mode")
    @classmethod
    def validate_payment_mode(cls, v: str) -> str:
        """Проверяет корректность режима оплаты."""
        allowed = {"sandbox", "production"}
        if v not in allowed:
            raise ValueError(f"payment_mode must be one of {allowed}, got '{v}'")
        return v

    # SMTP (Email)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # pydantic_settings configuration
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Глобальный объект настроек приложения
settings = Settings()
