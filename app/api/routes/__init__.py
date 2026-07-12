"""Инициализация и агрегация всех REST эндпоинтов."""

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.keys import router as keys_router
from app.api.routes.payments import router as payments_router
from app.api.routes.users import router as users_router
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(payments_router, prefix="/payments", tags=["payments"])
api_router.include_router(keys_router, prefix="/keys", tags=["keys"])
api_router.include_router(users_router, prefix="/users", tags=["users"])

# Sandbox-роутер подключается только в режиме разработки
if settings.payment_mode == "sandbox":
    from app.api.routes.sandbox import router as sandbox_router
    api_router.include_router(
        sandbox_router,
        prefix="/payments/sandbox",
        tags=["payments:sandbox"]
    )
