"""API роутер для управления ключами."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from schemas.keys import AWGKeyCreate, XrayKeyCreate
from services.awg_manager import awg_manager
from services.xray_manager import xray_manager

router = APIRouter()


class SuccessResponse(BaseModel):
    success: bool
    message: str


@router.post("/awg", response_model=SuccessResponse)
async def add_awg_key(key_data: AWGKeyCreate):
    """Добавление ключа AmneziaWG."""
    if awg_manager.add_peer(key_data):
        return {"success": True, "message": "AWG peer added successfully"}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to add AWG peer (already exists?)")


@router.delete("/awg/{public_key}", response_model=SuccessResponse)
async def remove_awg_key(public_key: str):
    """Удаление ключа AmneziaWG."""
    if awg_manager.remove_peer(public_key):
        return {"success": True, "message": "AWG peer removed successfully"}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AWG peer not found")


@router.post("/xray", response_model=SuccessResponse)
async def add_xray_key(key_data: XrayKeyCreate):
    """Добавление клиента Xray."""
    if xray_manager.add_client(key_data):
        return {"success": True, "message": "Xray client added successfully"}
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add Xray client")


@router.delete("/xray/{email}", response_model=SuccessResponse)
async def remove_xray_key(email: str):
    """Удаление клиента Xray."""
    if xray_manager.remove_client(email):
        return {"success": True, "message": "Xray client removed successfully"}
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove Xray client")
