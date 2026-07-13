"""Фоновые задачи для сбора статистики с нод."""

import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.db.repositories.server import ServerRepository
from app.db.repositories.key import KeyRepository
from app.core.config import settings

async def collect_stats_from_node(server_ip: str, token: str) -> dict:
    """Собирает статистику с одной ноды."""
    agent_url = f"http://{server_ip}:8081/api/stats"
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(agent_url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()
        except httpx.RequestError as e:
            print(f"Failed to fetch stats from {server_ip}: {e}")
            
    return {"awg": {}, "xray": {}}

async def run_stats_collection() -> None:
    """Функция для периодического запуска (arq/celery)."""
    async with async_session_maker() as session:
        server_repo = ServerRepository(session)
        key_repo = KeyRepository(session)
        
        servers = await server_repo.get_all()
        active_servers = [s for s in servers if getattr(s, "status", "active") == "active"]
        
        agent_token = getattr(settings, "AGENT_TOKEN", "supersecret")
        
        for server in active_servers:
            ip = getattr(server, "ip_address", "127.0.0.1")
            stats = await collect_stats_from_node(ip, agent_token)
            
            # Обработка AWG статистики
            for pubkey, traffic in stats.get("awg", {}).items():
                print(f"AWG Traffic for {pubkey}: RX={traffic['rx']} TX={traffic['tx']}")
                # В реальном приложении: найти ключ по pubkey и списать трафик у пользователя
                
            # Обработка Xray статистики
            for email, traffic in stats.get("xray", {}).items():
                print(f"Xray Traffic for {email}: RX={traffic['rx']} TX={traffic['tx']}")
                # В реальном приложении: найти ключ по client_uuid (через email) и списать трафик

if __name__ == "__main__":
    asyncio.run(run_stats_collection())
