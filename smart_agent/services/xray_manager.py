"""Менеджер конфигурации Xray (через gRPC CLI)."""

import json
import tempfile
import subprocess
import os

from core.config import settings
from schemas.keys import XrayKeyCreate


class XrayManager:
    """Управление клиентами Xray через xray api CLI."""

    def __init__(self, api_host: str = settings.XRAY_API_HOST, api_port: int = settings.XRAY_API_PORT):
        self.api_server = f"{api_host}:{api_port}"

    def _run_xray_api(self, *args) -> tuple[bool, str]:
        """Запуск команды xray api."""
        cmd = ["xray", "api"] + list(args)
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True
            )
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, f"{e.stdout}\n{e.stderr}"

    def add_client(self, client: XrayKeyCreate, inbound_tag: str = "vless-in") -> bool:
        """Добавление клиента через Xray API (gRPC CLI)."""
        payload = {
            "inboundTag": inbound_tag,
            "users": [
                {
                    "id": client.uuid,
                    "email": client.email,
                    "flow": "xtls-rprx-vision"
                }
            ]
        }

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
            json.dump(payload, f)
            temp_path = f.name

        try:
            success, output = self._run_xray_api("adu", f"--server={self.api_server}", temp_path)
            if not success:
                print(f"Xray add_client error: {output}")
            return success
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def remove_client(self, email: str, inbound_tag: str = "vless-in") -> bool:
        """Удаление клиента."""
        success, output = self._run_xray_api("rmu", f"--server={self.api_server}", f"-tag={inbound_tag}", email)
        if not success:
            print(f"Xray remove_client error: {output}")
        return success

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Получение статистики.
        Возвращает: {'user_email': {'rx': 123, 'tx': 456}}
        """
        success, output = self._run_xray_api("statsquery", f"--server={self.api_server}")
        if not success:
            print(f"Xray statsquery error: {output}")
            return {}

        # Формат вывода `xray api statsquery` (обычно возвращает JSON или proto txt).
        # По умолчанию он возвращает JSON с массивом 'stat'.
        stats = {}
        try:
            data = json.loads(output)
            for st in data.get("stat", []):
                name = st.get("name", "")
                value = int(st.get("value", 0))

                # Имя имеет формат: user>>>email>>>traffic>>>downlip
                # Или user>>>email>>>traffic>>>uplink
                if name.startswith("user>>>"):
                    parts = name.split(">>>")
                    if len(parts) >= 4:
                        email = parts[1]
                        metric = parts[3]  # downlink или uplink

                        if email not in stats:
                            stats[email] = {"rx": 0, "tx": 0}

                        if metric == "downlink":
                            stats[email]["tx"] = value  # downlink сервера = tx
                        elif metric == "uplink":
                            stats[email]["rx"] = value  # uplink сервера = rx

            return stats
        except json.JSONDecodeError:
            print(f"Failed to parse Xray stats: {output}")
            return {}


xray_manager = XrayManager()
