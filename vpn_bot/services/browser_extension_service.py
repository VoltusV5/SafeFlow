"""Текст инструкции SmartProxy для браузера (данные из .env)."""

from __future__ import annotations

from html import escape

from vpn_bot.config import Settings

from vpn_bot.services.telegram_proxy_service import (
    is_http_proxy_configured,
    resolve_telegram_proxy_host,
)

SMARTPROXY_CHROME_STORE_URL = (
    "https://chromewebstore.google.com/detail/smartproxy/"
    "jogcnplbkgkfdakgdenhlpcfhjioidoj?hl=ru"
)
SMARTPROXY_FIREFOX_URL = (
    "https://addons.mozilla.org/ru/firefox/addon/smartproxy/"
)
SMARTPROXY_GUIDE_PDF_NAME = "Инструкция_SmartProxy.pdf"


def format_smartproxy_browser_message(settings: Settings) -> str:
    host = resolve_telegram_proxy_host(settings)
    if not host or not is_http_proxy_configured(settings):
        return (
            "Расширение для браузера пока недоступно: на сервере не настроен "
            "HTTP-прокси (TELEGRAM_HTTP_PROXY_USER, TELEGRAM_HTTP_PROXY_PASSWORD) "
            "или не задан адрес сервера. Обратитесь к администратору."
        )

    port = settings.telegram_http_proxy_port
    user = (settings.telegram_http_proxy_user or "").strip()
    pw = (settings.telegram_http_proxy_password or "").strip()
    chrome_h = escape(SMARTPROXY_CHROME_STORE_URL, quote=True)
    ff_h = escape(SMARTPROXY_FIREFOX_URL, quote=True)

    return (
        "<b>Инструкция по установке</b>\n\n"
        "<b>1.</b> Скачать расширение в официальном магазине:\n"
        f'• Chrome (все браузеры кроме Firefox): '
        f'<a href="{chrome_h}">SmartProxy в Chrome Web Store</a>\n'
        f'• Firefox: <a href="{ff_h}">SmartProxy для Firefox</a>\n\n'
        "<b>2.</b> Зайти в настройки расширения → "
        "<b>Прокси-серверы</b> → <b>Добавить сервер</b>\n\n"
        "<b>3.</b> Вводим данные:\n"
        f"• Тип: <b>HTTP</b>\n"
        f"• Сервер: <code>{escape(host)}</code>\n"
        f"• Порт: <code>{port}</code>\n"
        f"• Логин: <code>{escape(user)}</code>\n"
        f"• Пароль: <code>{escape(pw)}</code>\n\n"
        "<b>4.</b> Сохранить → кнопка <b>Сохранить изменения</b>!\n\n"
        "<b>5.</b> В панели расширений SmartProxy выбрать "
        "<b>«всегда включен»</b>."
    )
