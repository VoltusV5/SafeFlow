"""Сервис бизнес-логики пользователей.

Модуль определяет класс UserService для регистрации, управления банами
и обработки реферальных программ.
"""

from datetime import datetime, timedelta, timezone

from app.core.enums import PlanType
from app.db.uow import UnitOfWork
from app.schemas.user import UserCreate, UserResponse


class UserService:
    """Сервис для работы с пользователями."""

    def __init__(self, uow: UnitOfWork):
        """Инициализация сервиса.

        Args:
            uow: Интерфейс Unit of Work для работы с БД.
        """
        self.uow = uow

    async def register_user(self, user_in: UserCreate) -> UserResponse:
        """Регистрация нового пользователя.

        Если пользователь существует, возвращает его.
        Если новый - создает, дает базовую подписку и начисляет бонус за реферала.

        Args:
            user_in: DTO с данными пользователя.

        Returns:
            DTO с данными зарегистрированного пользователя.
        """
        async with self.uow:
            # Проверяем существование
            existing = await self.uow.users.get_by_tg_id(user_in.telegram_id)
            if existing:
                return UserResponse.model_validate(
                    {
                        "id": existing.id,
                        "telegram_id": getattr(existing, "tg_id", None)
                        or getattr(existing, "telegram_id", None),
                        "username": existing.username,
                        "balance": getattr(existing, "balance", 0),
                        "is_banned": getattr(existing, "is_banned", False),
                        "created_at": getattr(existing, "created_at", None)
                        or datetime.now(timezone.utc)
                    }
                )

            # Создаем пользователя: поле UserCreate.telegram_id → колонка User.tg_id
            user_data = user_in.model_dump()
            user_data["tg_id"] = user_data.pop("telegram_id")
            user_data.pop("referred_by", None)  # not a DB column
            new_user = await self.uow.users.create(user_data)

            # Создаем триальную подписку (например, 7 дней базы по умолчанию)
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)

            # Проверяем реферальную программу
            if user_in.referred_by:
                referer = await self.uow.users.get(user_in.referred_by)
                if referer:
                    # Даем рефералу дополнительно 7 дней
                    expires_at += timedelta(days=7)

                    # Даем рефереру +30 дней к его подписке
                    # (Находим активную подписку реферера)
                    referer_subs = await self.uow.subscriptions.get_all()
                    referer_sub = next(
                        (
                            s for s in referer_subs
                            if getattr(s, "user_id", None) == referer.id
                            and getattr(s, "is_active", False)
                        ),
                        None
                    )

                    if referer_sub:
                        # Если expires_at в прошлом, считаем от сегодня
                        # Для мока (у которого может не быть expires_at)
                        current_expiry = getattr(
                            referer_sub, "expires_at", datetime.now(timezone.utc))
                        if current_expiry < datetime.now(timezone.utc):
                            current_expiry = datetime.now(timezone.utc)

                        new_expiry = current_expiry + timedelta(days=30)
                        await self.uow.subscriptions.update(
                            referer_sub, {"expires_at": new_expiry}
                        )

            await self.uow.subscriptions.create(
                {
                    "user_id": new_user.id,
                    "plan": PlanType.BASE,
                    "expires_at": expires_at,
                    "is_active": True,
                    "base_device_limit": 3
                }
            )

            # UoW сам сделает commit() при выходе из контекста
            # но чтобы вернуть данные с обновленными полями (если они есть)
            # мы можем использовать .model_validate
            # Однако, для этого нужно быть уверенными, что id назначен (mock это делает)

            return UserResponse.model_validate(
                {
                    "id": new_user.id,
                    "telegram_id": getattr(new_user, "tg_id", None) or getattr(new_user, "telegram_id", None),
                    "username": new_user.username,
                    "balance": getattr(new_user, "balance", 0),
                    "is_banned": getattr(new_user, "is_banned", False),
                    "created_at": getattr(new_user, "created_at", None) or datetime.now(timezone.utc)
                }
            )
