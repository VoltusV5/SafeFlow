from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.db.models.base import Base

class BypassRule(Base):
    """
    Модель для хранения правил обхода блокировок.
    Второй разработчик может добавлять сюда нужные колонки.
    """
    __tablename__ = "bypass_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    domain = Column(String, nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    # Связь с пользователем
    user = relationship("User", backref="bypass_rules")
