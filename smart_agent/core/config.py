"""Настройки конфигурации Smart Agent."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Основные настройки агента."""

    AGENT_TOKEN: str = "supersecret"
    AWG_CONFIG_PATH: str = "/etc/amnezia/awg/wg0.conf"
    XRAY_API_HOST: str = "xray"
    XRAY_API_PORT: int = 8080

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
