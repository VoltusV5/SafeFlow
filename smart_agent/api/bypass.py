from fastapi import APIRouter, Depends, HTTPException

from smart_agent.services.bypass_manager import BypassManager

router = APIRouter(prefix="/bypass", tags=["bypass"])
manager = BypassManager()

@router.post("/rules")
async def add_bypass_rule(domain: str, action: str):
    """
    Эндпоинт для применения правил обхода блокировок.
    Второй разработчик может принимать здесь список доменов или конкретные правила.
    """
    try:
        await manager.apply_domain_rule(domain, action)
        return {"status": "success", "message": f"Rule {action} applied for {domain}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
