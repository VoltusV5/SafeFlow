from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.models.base import Base

class Key(Base):
    __tablename__ = "keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    server_id: Mapped[int] = mapped_column(Integer, ForeignKey("servers.id"), nullable=False)
    protocol: Mapped[str] = mapped_column(String, nullable=False)
    internal_ip: Mapped[str | None] = mapped_column(String, nullable=True)
    client_uuid: Mapped[str | None] = mapped_column(String, nullable=True)
    config_data: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="active")

    # relationships
    user = relationship("User", back_populates="keys")
    server = relationship("Server", back_populates="keys")
