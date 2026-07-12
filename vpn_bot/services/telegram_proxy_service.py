"""Данные для MTProto proxy и SOCKS5 (настройка на сервере + .env)."""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from vpn_bot.config import Settings


def _host_from_wg_endpoint(wg_endpoint: str) -> str | None:
    ep = (wg_endpoint or "").strip()
    if not ep:
        return None
    if "]:" in ep:
        return ep.split("]:", 1)[0].lstrip("[")
    if ep.count(":") > 1 and "[" in ep:
        return ep.split("]", 1)[0].lstrip("[")
    if ":" in ep:
        return ep.rsplit(":", 1)[0].strip()
    return ep


def resolve_telegram_proxy_host(settings: Settings) -> str | None:
    h = (settings.telegram_proxy_host or "").strip()
    if h:
        return h
    ph = (settings.public_host or "").strip()
    if ph:
        return ph
    return _host_from_wg_endpoint(settings.wg_endpoint)


def is_telegram_proxy_configured(settings: Settings) -> bool:
    if not (settings.telegram_mtproto_secret or "").strip():
        return False
    if not (settings.telegram_socks_user or "").strip():
        return False
    if not (settings.telegram_socks_password or "").strip():
        return False
    return resolve_telegram_proxy_host(settings) is not None


def is_http_proxy_configured(settings: Settings) -> bool:
    if not (settings.telegram_http_proxy_user or "").strip():
        return False
    if not (settings.telegram_http_proxy_password or "").strip():
        return False
    return resolve_telegram_proxy_host(settings) is not None


def build_mtproto_telegram_https_link(settings: Settings) -> str | None:
    """Основной порт MTProto (обратная совместимость)."""
    return build_mtproto_telegram_https_link_for_port(
        settings, settings.telegram_mtproto_port
    )


def build_mtproto_telegram_https_link_for_port(
    settings: Settings, port: int
) -> str | None:
    """HTTPS-ссылка t.me/proxy для указанного порта (тот же секрет)."""
    host = resolve_telegram_proxy_host(settings)
    secret = (settings.telegram_mtproto_secret or "").strip()
    if not host or not secret or port <= 0:
        return None
    q = urlencode(
        {
            "server": host,
            "port": str(port),
            "secret": secret,
        }
    )
    return f"https://t.me/proxy?{q}"


def iter_mtproto_ports(settings: Settings) -> list[int]:
    """Порты MTProto для отображения: основной + alt, без дубликатов."""
    raw = [
        settings.telegram_mtproto_port,
        settings.telegram_mtproto_port_alt1,
        settings.telegram_mtproto_port_alt2,
    ]
    seen: set[int] = set()
    out: list[int] = []
    for p in raw:
        if p > 0 and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def build_socks_telegram_https_link(settings: Settings) -> str | None:
    """Основной порт SOCKS5 (обратная совместимость)."""
    return build_socks_telegram_https_link_for_port(
        settings, settings.telegram_socks_port
    )  # noqa: E501


def build_socks_telegram_https_link_for_port(
    settings: Settings, port: int
) -> str | None:
    """Ссылка t.me/socks для указанного порта (те же логин и пароль)."""
    host = resolve_telegram_proxy_host(settings)
    user = (settings.telegram_socks_user or "").strip()
    pw = (settings.telegram_socks_password or "").strip()
    if not host or not user or not pw or port <= 0:
        return None
    q = urlencode(
        {
            "server": host,
            "port": str(port),
            "user": user,
            "pass": pw,
        }
    )
    return f"https://t.me/socks?{q}"


def iter_socks_ports(settings: Settings) -> list[int]:
    """Порты SOCKS5 для отображения: основной + alt, без дубликатов."""
    raw = [
        settings.telegram_socks_port,
        settings.telegram_socks_port_alt1,
        settings.telegram_socks_port_alt2,
    ]
    seen: set[int] = set()
    out: list[int] = []
    for p in raw:
        if p > 0 and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def format_telegram_proxy_message(settings: Settings) -> str:
    host = resolve_telegram_proxy_host(settings)
    if not host:
        return (
            "Прокси для Telegram пока не настроен: в .env нужен "
            "TELEGRAM_PROXY_HOST или PUBLIC_HOST / WG_ENDPOINT с адресом сервера."  # noqa: E501
        )
    if not is_telegram_proxy_configured(settings):
        return (
            "Прокси для Telegram на сервере ещё не подключены или не заданы переменные "  # noqa: E501
            "TELEGRAM_MTPROTO_SECRET, TELEGRAM_SOCKS_USER, TELEGRAM_SOCKS_PASSWORD. "  # noqa: E501
            "Обратитесь к администратору."
        )

    lines = [
        "Можно выбрать любой из вариантов ниже. "
        "Обычно по Wi‑Fi работает нормально; через мобильный интернет заметно хуже.",  # noqa: E501
        "",
        "MTProto:",
    ]
    for port in iter_mtproto_ports(settings):
        link = build_mtproto_telegram_https_link_for_port(settings, port)
        if link:
            href = escape(link, quote=True)
            lines.append(f'<a href="{href}">Подключить MTProto (порт {port})</a>')
            # noqa: W293, E114, E116
    # Добавляем 4-ый прокси "MTProto РФ" с маскировкой под vk.com
    ru_secret = "7lYrylrQIe6G7B_fgSA1Eot2ay5jb20"
    ru_port = 4433
    q_ru = urlencode(
        {"server": host, "port": str(ru_port), "secret": ru_secret}
    )  # noqa: E501
    link_ru = f"https://t.me/proxy?{q_ru}"
    href_ru = escape(link_ru, quote=True)
    lines.append(
        f'<a href="{href_ru}">Подключить MTProto РФ (порт {ru_port})</a>'
    )  # noqa: E501

    if len(lines) == 3:
        lines.append("Подключить MTProto")

    lines.extend(["", "SOCKS5 для Telegram:"])
    for port in iter_socks_ports(settings):
        link = build_socks_telegram_https_link_for_port(settings, port)
        if link:
            href = escape(link, quote=True)
            lines.append(f'<a href="{href}">Подключить SOCKS5 (порт {port})</a>')
    if lines[-1] == "SOCKS5 для Telegram:":
        lines.append("Подключить SOCKS5")

    return "\n".join(lines)
