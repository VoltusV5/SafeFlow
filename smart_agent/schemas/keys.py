"""Схемы данных для API Агента."""

from pydantic import BaseModel, Field


class AWGKeyCreate(BaseModel):
    public_key: str = Field(..., description="Public Key пира")
    preshared_key: str | None = Field(None, description="Preshared Key пира (опционально)")
    allowed_ip: str = Field(..., description="Внутренний IP пира (например, 10.8.0.2/32)")


class XrayKeyCreate(BaseModel):
    uuid: str = Field(..., description="UUID клиента Xray")
    email: str = Field(..., description="Уникальный email (ID) клиента для идентификации в Xray")
