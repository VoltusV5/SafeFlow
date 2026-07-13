"""Точка входа Smart Agent."""

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import settings
from api import keys, stats, bypass

app = FastAPI(
    title="SafeFlow Smart Agent",
    description="Легковесный агент для управления VPN-нодой (AWG & Xray)",
    version="1.0.0"
)

security = HTTPBearer()


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Проверка статического Bearer токена."""
    if credentials.credentials != settings.AGENT_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True


# Подключаем роутеры с глобальной защитой
app.include_router(keys.router, prefix="/api/keys", tags=["Keys"], dependencies=[Depends(verify_token)])
app.include_router(stats.router, prefix="/api/stats", tags=["Stats"], dependencies=[Depends(verify_token)])
app.include_router(bypass.router, prefix="/api/bypass", tags=["Bypass"], dependencies=[Depends(verify_token)])


@app.get("/health", tags=["System"])
async def health_check():
    """Проверка состояния агента."""
    return {"status": "ok", "service": "smart_agent"}
