"""API роутер для сбора статистики."""

from fastapi import APIRouter
from pydantic import BaseModel

from services.awg_manager import awg_manager
from services.xray_manager import xray_manager

router = APIRouter()


class TrafficStat(BaseModel):
    rx: int
    tx: int


class StatsResponse(BaseModel):
    awg: dict[str, TrafficStat]
    xray: dict[str, TrafficStat]


@router.get("/", response_model=StatsResponse)
async def get_all_stats():
    """Получение статистики по всем протоколам."""
    awg_stats = awg_manager.get_stats()
    xray_stats = xray_manager.get_stats()

    return {
        "awg": awg_stats,
        "xray": xray_stats
    }
