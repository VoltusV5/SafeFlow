MAX_PASSWORD_FAIL_ATTEMPTS = 50

# Главное меню (ReplyKeyboard)
MAIN_MENU_BUTTON_TELEGRAM_PROXY = "Telegram proxy"
MAIN_MENU_BUTTON_BROWSER_EXTENSION = "Расширение в браузере"
MAIN_MENU_BUTTON_SUPPORT_DONATE = "Техподдержка / донат"
MAIN_MENU_BUTTON_BACK_TO_MAIN = "◀️ Главное меню"

MIN_TELEGRAM_STARS_DONATION = 1
MAX_TELEGRAM_STARS_DONATION = 25000

MAX_AMNEZIA_WG_KEYS_PER_24H = 50
AMNEZIA_WG_RATE_LIMIT_HOURS = 24

BANDWIDTH_FAIR_SHARE_THRESHOLD_MBPS = 780
BANDWIDTH_FAIR_SHARE_POOL_MBPS = 750
BANDWIDTH_MAX_PER_USER_MBPS = 500
CPU_FAIR_SHARE_PERCENT = 98.0
WG_ACTIVE_HANDSHAKE_SEC = 2500
# Окно «был handshake» для метрик (дайджест): последние 24 часа
WG_HANDSHAKE_LAST_24H_SEC = 86400

DAEMON_NET_INTERFACE = "eth0"
DAEMON_WG_INTERFACE = "awg0"

# Кнопки «Сообщить о проблеме» (кроме «Другое» — там свой текст в keyboards)
REPORT_PROBLEM_PRESETS: tuple[str, ...] = (
    "Не подключается",
    "Подключается, но ничего не работает",
    "Не удаётся добавить ключ, файл или QR в приложение",
)
