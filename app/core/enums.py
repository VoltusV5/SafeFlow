"""Общие перечисления (Enums) проекта.

Модуль содержит константы и перечисления, используемые в приложении.
"""

from enum import Enum


class Country(str, Enum):
    """Доступные страны размещения VPN серверов."""

    POLAND = "Poland"
    SWEDEN = "Sweden"
    USA = "USA"


class Protocol(str, Enum):
    """Поддерживаемые протоколы VPN."""

    XRAY = "Xray"
    AWG = "AWG"
