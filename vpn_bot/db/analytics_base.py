from sqlalchemy.orm import DeclarativeBase


class BaseAnalytics(DeclarativeBase):
    """Отдельная БД: трафик и метрики (append-heavy), без FK на основную БД."""
