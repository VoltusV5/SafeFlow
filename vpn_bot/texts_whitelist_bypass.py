"""Тексты для «Дополнительный VPN провайдер» и тестового vk-turn (HTML)."""

from __future__ import annotations

from html import escape

# Мультиссылка и ключи SS (Chrome) — одни и те же URL в href и в тексте ссылки для копирования
_MULTILINK_HYNET = "https://hynet.space/s/KXd8eFcDBngjdHMFSXYicX9x"
_CHR_SS_RU = (
    "ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNToyOE1ZRVRiZlQwWHBtenR0VHBTdjZn@212.233.97.101:2060"
    "#%F0%9F%87%B7%F0%9F%87%BA%20SHADOWSOCKS%20-%20%D0%A0%D0%BE%D1%81%D1%81%D0%B8%D1%8F%20%28"
    "YouTube%20%D0%B1%D0%B5%D0%B7%20%D1%80%D0%B5%D0%BA%D0%BB%D0%B0%D0%BC%D1%8B%29"
)
_CHR_SS_NL = (
    "ss://Y2hhY2hhMjAtaWV0Zi1wb2x5MTMwNToyOE1ZRVRiZlQwWHBtenR0VHBTdjZn@195.189.96.216:2060"
    "#%F0%9F%87%B3%F0%9F%87%B1%20SHADOWSOCKS%20-%20%D0%9D%D0%B8%D0%B4%D0%B5%D1%80%D0%BB%D0%B0%D0%BD%D0%B4%D1%8B"
)

_CHROME_PLATFORM_CHUNK = (
    "<b>Chrome</b>\n\n"
    "1. Установите клиент Shadowsocks в магазине Chrome:\n"
    '<a href="https://chromewebstore.google.com/detail/shadowsocks/fnhhahhihediajgefcnlpdmnogndblbi">Shadowsocks</a>\n\n'
    "2. Вставьте мультиссылку в свой VPN. Мультиссылка:\n"
    f'<a href="{escape(_MULTILINK_HYNET, quote=True)}">{escape(_MULTILINK_HYNET)}</a>\n\n'
    "<b>Ключи Shadowsocks</b>\n\n"
    "Россия:\n"
    f'<a href="{escape(_CHR_SS_RU, quote=True)}">{escape(_CHR_SS_RU)}</a>\n\n'
    "Нидерланды:\n"
    f'<a href="{escape(_CHR_SS_NL, quote=True)}">{escape(_CHR_SS_NL)}</a>\n'
)

# Первый экран: без «вывала» длинных блоков — только кратко + кнопка «Инструкции»
WHITELIST_BYPASS_INTRO_HTML = (
    "<b>Второй VPN провайдер (hynet.space)</b>\n\n"
    "<b>Быстрый старт</b>\n"
    "1. Установите VPN-приложение: v2RayTun или Happ "
    "(подробнее по кнопке «Инструкции»).\n"
    "2. Вставьте мультиссылку в свой VPN. Обычно в приложении кнопка «+» → "
    "«Вставить из буфера обмена», Мультиссылка:\n"
    f'<a href="{escape(_MULTILINK_HYNET, quote=True)}">{escape(_MULTILINK_HYNET)}</a>\n\n'
    "Подробные шаги по вашей системе — в разделе «Инструкции»."
)

# Кнопки выбора системы: (callback slug, подпись)
WHITELIST_PLATFORM_MENU: tuple[tuple[str, str], ...] = (
    ("win", "Windows"),
    ("and", "Android"),
    ("ios", "iOS"),
    ("mac", "macOS"),
    ("lin", "Linux"),
    ("chr", "Chrome"),
    ("tv", "Smart TV"),
    ("atv", "Apple TV"),
    ("rtr", "Роутеры"),
)

WHITELIST_INSTR_MENU_HTML = (
    "<b>Инструкции</b>\n\n"
    "Выберите систему — текст покажется в этом же сообщении."
)

VKTURN_TEST_INTRO_HTML = (
    "<b>Тестовый обход белых списков (vk-turn + Happ/v2RayTun)</b>\n\n"
    "Бот выдаст команду запуска Termux-клиента и локальную VLESS-ссылку для Happ/v2RayTun."
)

VKTURN_VK_LINK = "https://vk.com/call/join/Sduu0nMXydK0Fy4ybm9ULEb4lQqGEDUXN1O0waTfl5o"

# Сообщения по платформе: список частей (каждая в пределах лимита Telegram)
WHITELIST_PLATFORM_CHUNKS: dict[str, list[str]] = {
    "win": [
        (
            "<b>Windows</b>\n\n"
            "1. <b>Happ</b> — скачайте и установите приложение:\n"
            '<a href="https://hynet.space/file/Happ.x64.exe">Happ.x64.exe</a>\n\n'
            "<b>v2RayTun</b>\n"
            '<a href="https://hynet.space/file/v2RayTun_Setup.exe">v2RayTun_Setup.exe</a>\n'
        ),
    ],
    "and": [
        (
            "<b>Android</b>\n\n"
            "1. <b>Happ</b> — установите через Google Play "
            '<a href="https://play.google.com/store/apps/details?id=com.happproxy">Google Play</a> '
            "или APK:\n"
            '<a href="https://hynet.space/file/Happ.apk">Happ.apk</a>\n\n'
            "<b>v2RayTun</b>\n"
            '<a href="https://play.google.com/store/apps/details?id=com.v2raytun.android&amp;pcampaignid=web_share">Google Play</a>\n\n'
            "<b>v2rayNG</b>\n"
            '<a href="https://hynet.space/file/v2rayNG_1.10.31_universal.apk">v2rayNG_1.10.31_universal.apk</a>\n'
        ),
    ],
    "ios": [
        (
            "<b>iOS</b>\n\n"
            "1. <b>Happ</b> — App Store (глобальная или версия для России):\n"
            '<a href="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215">Глобальная</a>\n'
            '<a href="https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973">Россия</a>\n\n'
            "<b>v2RayTun</b>\n"
            '<a href="https://apps.apple.com/us/app/v2raytun/id6476628951">App Store</a>\n\n'
            "• <b>Streisand</b> (App Store) — iPhone, iPad.\n"
            "• <b>Karing</b> (App Store) — iPhone, iPad, Mac, Apple TV.\n"
            "• <b>V2Box</b> (App Store) — для VLESS нужно указать fingerprint (iPhone, iPad, Mac).\n"
            "• <b>FoXray</b> (App Store) — iPhone, iPad, Mac.\n"
        ),
    ],
    "mac": [
        (
            "<b>macOS</b>\n\n"
            "1. <b>Happ</b> — App Store (глобальная / Россия) или DMG:\n"
            '<a href="https://apps.apple.com/us/app/happ-proxy-utility/id6504287215">Глобальная</a>\n'
            '<a href="https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973">Россия</a>\n'
            '<a href="https://hynet.space/file/Happ.macOS.universal.dmg">Happ.macOS.universal.dmg</a>\n\n'
            "<b>v2RayTun</b>\n"
            '<a href="https://apps.apple.com/us/app/v2raytun/id6476628951">App Store</a>\n'
        ),
    ],
    "lin": [
        (
            "<b>Linux</b>\n\n"
            "<b>Happ</b> — скачайте deb и установите.\n\n"
            "Также: <b>Nekoray</b> и другие клиенты с поддержкой вашего протокола.\n"
        ),
    ],
    "chr": [_CHROME_PLATFORM_CHUNK],
    "tv": [
        (
            "<b>Smart TV — Android TV / Google TV</b>\n\n"
            "1. Установите <b>v2rayTun</b> из Google Play на ТВ. Если магазина нет — установите APK вручную.\n"
            "2. Откройте на ТВ сайт <a href=\"https://hynet.space\">hynet.space</a> в браузере "
            "(при необходимости установите браузер, например Яндекс Браузер для ТВ).\n"
            "Авторизуйтесь по QR (Войти → по QR-коду). Выберите сервер → «Копировать» на нужном ключе (например VMess).\n"
            "В v2rayTun: Управление → Импорт из буфера обмена.\n"
            "3. Включите VPN значком подключения.\n"
        ),
    ],
    "atv": [
        (
            "<b>Apple TV</b>\n\n"
            "1. Установите <b>Karing</b> на Apple TV и на iPhone (на приставке без iPhone настроить сложно).\n"
            "Скопируйте ключ доступа из личного кабинета (например VLESS) и добавьте в Karing на iPhone.\n"
            "2. На ТВ откройте Karing и свяжите с iPhone по инструкции на экране.\n"
            "3. Проверьте статус в Karing и открытие нужных ресурсов. При старых iOS/tvOS обновите ОС или используйте другое устройство.\n"
        ),
    ],
    "rtr": [
        (
            "<b>Роутеры</b>\n\n"
            "Если нужен JSON-файл, перейдите в сервис <b>VPN 2 JSON</b>.\n\n"
            "Все протоколы поддерживают широкий спектр устройств и роутеров — это помогает настроить "
            "надёжное и безопасное подключение.\n\n"
            "<b>Shadowsocks</b> поддерживается на роутерах с возможностью ставить или менять прошивки. "
            "Часто используют OpenWRT, DD-WRT или Padavan. Примеры моделей:\n\n"
            "• <b>TP-Link Archer C7</b> и выше — OpenWRT/DD-WRT, настройка Shadowsocks через веб-интерфейс или CLI.\n"
            "• <b>ASUS</b> (например RT-AC68U, RT-AX58U) — прошивка Merlin, Shadowsocks через веб-интерфейс.\n"
            "• <b>Xiaomi</b> (Router 3, 4A, 4G) — Padavan или OpenWRT с Shadowsocks.\n"
            "• <b>Netgear</b> (R7000, R7800) — DD-WRT, OpenWRT или AdvancedTomato.\n"
            "• <b>GL.iNet</b> (GL-MT300N, GL-AR750S, GL-B1300) — ориентированы на VPN, Shadowsocks из коробки или доп. настройка.\n"
            "• <b>Tenda AC18</b> — Padavan и OpenWRT.\n"
        ),
        (
            "<b>VMess и VLESS</b> — на многих роутерах с OpenWRT, FRITZ!Box и Linux-прошивками; настройка через веб-интерфейс или CLI.\n\n"
            "<b>Trojan</b> — современные роутеры с OpenWRT/DD-WRT; у части GL.iNet — встроенная поддержка.\n\n"
            "<b>Важно:</b> для таких протоколов на роутере часто нужна <b>кастомная прошивка</b> — "
            "штатные прошивки большинства моделей не содержат эти VPN-клиенты.\n"
        ),
        (
            "<b>Прошивки и инструкции</b>\n"
            "OpenWRT · DD-WRT · AdvancedTomato · Padavan\n\n"
            "<b>Роутеры</b>\n"
            "Xiaomi — инструкция · Asus — инструкция · готовое решение — <b>HYNET Router</b>.\n\n"
            "Сейчас разрабатывается собственная прошивка для HYNET Router, ведутся переговоры с поставщиками из Китая. "
            "Планируется недорогой роутер как готовое решение: выгоднее аналогов по цене и возможностям. "
            "Достаточно купить HYNET Router, подключить кабелем к основному роутеру — и пользоваться интернетом "
            "без дополнительных прошивок и сложной настройки.\n\n"
            "Следите за обновлениями на сайте или в Telegram: "
            '<a href="https://t.me/hynet24">hynet24</a>.\n'
        ),
    ],
}
