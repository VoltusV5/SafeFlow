from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import List

class Settings(BaseSettings):
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
        """Returns asyncpg connection string for SQLAlchemy"""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # Security
    fernet_key: SecretStr

    # pydantic_settings configuration
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
