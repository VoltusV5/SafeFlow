"""Базовый репозиторий для работы с базой данных.

Предоставляет обобщенный класс BaseRepository с базовыми CRUD операциями.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Базовый класс репозитория.

    Реализует основные операции Create, Read, Update, Delete (CRUD)
    для указанной модели SQLAlchemy.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """Инициализация репозитория.

        Args:
            model: Класс модели SQLAlchemy, с которой будет работать репозиторий.  # noqa: E501
            session: Асинхронная сессия БД.
        """
        self.model = model
        self.session = session

    async def get(self, id: Any) -> Optional[ModelType]:
        """Получение записи по ее идентификатору.

        Args:
            id: Значение первичного ключа.

        Returns:
            Объект модели или None, если запись не найдена.
        """
        result = await self.session.execute(
            select(self.model).filter(self.model.id == id)
        )
        return result.scalars().first()

    async def get_all(self) -> List[ModelType]:
        """Получение всех записей из таблицы.

        Returns:
            Список всех объектов модели.
        """
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, obj_in: Dict[str, Any]) -> ModelType:
        """Создание новой записи в базе данных.

        Args:
            obj_in: Словарь с данными для создания объекта.

        Returns:
            Созданный объект модели.
        """
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def update(
        self, db_obj: ModelType, obj_in: Dict[str, Any]
    ) -> ModelType:
        """Обновление существующей записи.

        Args:
            db_obj: Объект модели, который необходимо обновить.
            obj_in: Словарь с новыми данными.

        Returns:
            Обновленный объект модели.
        """
        for field, value in obj_in.items():
            setattr(db_obj, field, value)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: Any) -> bool:
        """Удаление записи по идентификатору.

        Args:
            id: Значение первичного ключа.

        Returns:
            True, если запись была успешно удалена, иначе False.
        """
        result = await self.session.execute(
            sql_delete(self.model).where(self.model.id == id)
        )
        await self.session.flush()
        return result.rowcount > 0
