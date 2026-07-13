"""Менеджер конфигурации AmneziaWG (AWG)."""

import os
import subprocess
import re
from fastapi import HTTPException, status

from core.config import settings
from schemas.keys import AWGKeyCreate


class AWGManager:
    """Управление пирами AWG через редактирование wg0.conf и wg syncconf."""

    def __init__(self, config_path: str = settings.AWG_CONFIG_PATH):
        self.config_path = config_path

    def _read_config(self) -> str:
        """Чтение конфигурационного файла."""
        if not os.path.exists(self.config_path):
            return ""
        with open(self.config_path, "r", encoding="utf-8") as f:
            return f.read()

    def _write_config(self, content: str) -> None:
        """Запись конфигурационного файла."""
        # Убедимся, что директория существует
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _syncconf(self) -> None:
        """Применение изменений без перезапуска интерфейса."""
        try:
            # Требуется пакет wireguard-tools и права NET_ADMIN
            subprocess.run(
                ["wg", "syncconf", "wg0", self.config_path],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            # Если wg syncconf падает, это может быть критично (например, интерфейс wg0 не поднят)
            # Мы залогируем ошибку, но не будем крашить добавление ключа, так как конфиг уже сохранен
            print(f"Error running wg syncconf: {e.stderr}")
            # В реальном проде здесь можно рейзить HTTPException

    def add_peer(self, peer: AWGKeyCreate) -> bool:
        """Добавление нового пира в конфиг."""
        config = self._read_config()

        # Проверяем, есть ли уже такой PublicKey
        if f"PublicKey = {peer.public_key}" in config:
            return False  # Пир уже существует

        # Формируем блок пира
        peer_block = f"\n[Peer]\nPublicKey = {peer.public_key}\nAllowedIPs = {peer.allowed_ip}\n"
        if peer.preshared_key:
            peer_block += f"PresharedKey = {peer.preshared_key}\n"

        config += peer_block
        self._write_config(config)
        self._syncconf()

        return True

    def remove_peer(self, public_key: str) -> bool:
        """Удаление пира по PublicKey."""
        config = self._read_config()

        # Регулярное выражение для поиска блока [Peer] с конкретным ключом
        # Ищет от [Peer] до следующего [Peer] или конца файла
        pattern = re.compile(
            rf"\[Peer\]\s*\nPublicKey = {re.escape(public_key)}.*?(?=\n\[Peer\]|\Z)",
            re.DOTALL
        )

        if not pattern.search(config):
            return False  # Пир не найден

        new_config = pattern.sub("", config)
        self._write_config(new_config)
        self._syncconf()

        return True

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Получение статистики RX/TX по всем пирам."""
        try:
            result = subprocess.run(
                ["wg", "show", "all", "transfer"],
                check=True,
                capture_output=True,
                text=True
            )
            # Вывод имеет формат:
            # wg0   <public_key>    <rx_bytes>  <tx_bytes>
            stats = {}
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    pubkey = parts[1]
                    rx = int(parts[2])
                    tx = int(parts[3])
                    stats[pubkey] = {"rx": rx, "tx": tx}
            return stats
        except Exception as e:
            print(f"Failed to get AWG stats: {e}")
            return {}


awg_manager = AWGManager()
