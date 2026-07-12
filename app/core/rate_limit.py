"""Настройки Rate Limiting для приложения."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiter использует IP-адрес клиента как ключ
limiter = Limiter(key_func=get_remote_address)
