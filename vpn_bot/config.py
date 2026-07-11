from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BOT_AVATAR_ONLINE = str(_PROJECT_ROOT / "Src" / "ава для бота.png")
_DEFAULT_BOT_AVATAR_OFFLINE = str(_PROJECT_ROOT / "Src" / "бот на починке.jpg")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_password: str = Field(..., alias="BOT_PASSWORD")
    admin_ids_raw: str = Field(default="", alias="ADMIN_IDS")
    donation_alerts_url: str = Field(
        default="https://www.donationalerts.com/",
        validation_alias=AliasChoices("DONATION_ALERTS_URL", "DONATION_URL"),
    )
    tribute_url_web: str = Field(default="", alias="TRIBUTE_URL_WEB")
    tribute_url_tg: str = Field(default="", alias="TRIBUTE_URL_TG")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./bot_data.db",
        alias="DATABASE_URL",
    )
    analytics_database_url: str = Field(
        default="sqlite+aiosqlite:///./vpn_bot_analytics.db",
        alias="ANALYTICS_DATABASE_URL",
        description="Отдельная SQLite: traffic_log, host_metric_samples, daily_stats (append-heavy).",
    )
    generate_peer_script: str = Field(default="", alias="GENERATE_PEER_SCRIPT")
    replace_active_key_on_new: bool = Field(
        default=False,
        alias="REPLACE_ACTIVE_KEY_ON_NEW",
    )
    max_amnezia_keys_per_24h: int = Field(default=50, alias="MAX_AMNEZIA_KEYS_PER_24H")
    awg_iface: str = Field(default="awg0", alias="AWG_IFACE")
    awg_docker_container: str = Field(default="", alias="AWG_DOCKER_CONTAINER")
    awg_wg_iface: str = Field(default="wg0", alias="AWG_WG_IFACE")
    awg_wg_conf: str = Field(
        default="/opt/amnezia/awg/wg0.conf",
        alias="AWG_WG_CONF",
    )
    wg_server_public_key: str = Field(default="", alias="WG_SERVER_PUBLIC_KEY")
    wg_endpoint: str = Field(default="", alias="WG_ENDPOINT")
    public_host: str = Field(default="", alias="PUBLIC_HOST")
    telegram_proxy_host: str = Field(
        default="",
        alias="TELEGRAM_PROXY_HOST",
        description="Хост для MTProto/SOCKS (если пусто — PUBLIC_HOST или адрес из WG_ENDPOINT).",
    )
    telegram_mtproto_port: int = Field(default=8888, alias="TELEGRAM_MTPROTO_PORT")
    telegram_mtproto_port_alt1: int = Field(
        default=8443,
        alias="TELEGRAM_MTPROTO_PORT_ALT1",
        description="Доп. публичный порт MTProto (второй контейнер mtg); должен совпадать с compose.",
    )
    telegram_mtproto_port_alt2: int = Field(
        default=2053,
        alias="TELEGRAM_MTPROTO_PORT_ALT2",
        description="Доп. публичный порт MTProto (третий контейнер mtg); должен совпадать с compose.",
    )
    telegram_socks_port: int = Field(default=64945, alias="TELEGRAM_SOCKS_PORT")
    telegram_socks_port_alt1: int = Field(
        default=64946,
        alias="TELEGRAM_SOCKS_PORT_ALT1",
        description="Доп. порт SOCKS5; должен совпадать с compose.",
    )
    telegram_socks_port_alt2: int = Field(
        default=64947,
        alias="TELEGRAM_SOCKS_PORT_ALT2",
        description="Доп. порт SOCKS5; должен совпадать с compose.",
    )
    telegram_mtproto_secret: str = Field(default="", alias="TELEGRAM_MTPROTO_SECRET")
    telegram_socks_user: str = Field(default="", alias="TELEGRAM_SOCKS_USER")
    telegram_socks_password: str = Field(default="", alias="TELEGRAM_SOCKS_PASSWORD")
    telegram_http_proxy_port: int = Field(
        default=8086,
        alias="TELEGRAM_HTTP_PROXY_PORT",
        description="HTTP-прокси с авторизацией для Chrome (GOST); HTTPS сайты идут через CONNECT.",
    )
    telegram_http_proxy_user: str = Field(default="", alias="TELEGRAM_HTTP_PROXY_USER")
    telegram_http_proxy_password: str = Field(
        default="",
        alias="TELEGRAM_HTTP_PROXY_PASSWORD",
    )
    wg_client_dns: str = Field(default="1.1.1.1", alias="WG_CLIENT_DNS")
    wg_share_dns2: str = Field(default="1.0.0.1", alias="WG_SHARE_DNS2")
    amnezia_share_description: str = Field(
        default="SafeFlow",
        alias="AMNEZIA_SHARE_DESCRIPTION",
    )
    awg_client_mtu: str = Field(default="1376", alias="AWG_CLIENT_MTU")
    wg_client_ip_prefix: str = Field(default="10.8.0", alias="WG_CLIENT_IP_PREFIX")
    # Параллельный Amnezia AWG для новых ключей (2.x стек / отдельный порт). Пусто — как раньше только AWG_DOCKER_CONTAINER.
    awg2_docker_container: str = Field(default="", alias="AWG2_DOCKER_CONTAINER")
    awg2_wg_iface: str = Field(default="wg0", alias="AWG2_WG_IFACE")
    awg2_wg_conf: str = Field(
        default="/opt/amnezia/awg/wg0.conf",
        alias="AWG2_WG_CONF",
    )
    wg2_endpoint: str = Field(default="", alias="WG2_ENDPOINT")
    wg2_server_public_key: str = Field(default="", alias="WG2_SERVER_PUBLIC_KEY")
    wg2_client_ip_prefix: str = Field(default="10.8.2", alias="WG2_CLIENT_IP_PREFIX")

    docker_wireguard_container: str = Field(
        default="amnezia-wireguard",
        alias="DOCKER_WIREGUARD_CONTAINER",
    )
    docker_openvpn_container: str = Field(
        default="amnezia-openvpn",
        alias="DOCKER_OPENVPN_CONTAINER",
    )
    docker_openvpn_cloak_container: str = Field(
        default="amnezia-openvpn-cloak",
        alias="DOCKER_OPENVPN_CLOAK_CONTAINER",
    )
    docker_shadowsocks_container: str = Field(
        default="amnezia-shadowsocks",
        alias="DOCKER_SHADOWSOCKS_CONTAINER",
    )
    docker_ipsec_container: str = Field(
        default="amnezia-ipsec",
        alias="DOCKER_IPSEC_CONTAINER",
    )
    docker_xray_container: str = Field(
        default="amnezia-xray",
        alias="DOCKER_XRAY_CONTAINER",
    )
    wireguard_wg_conf: str = Field(
        default="/opt/amnezia/wireguard/wg0.conf",
        alias="WIREGUARD_WG_CONF",
    )
    wireguard_endpoint_port: int = Field(default=40560, alias="WIREGUARD_ENDPOINT_PORT")
    wireguard_client_prefix: str = Field(default="10.8.1", alias="WIREGUARD_CLIENT_PREFIX")
    openvpn_tcp_port: int = Field(default=49970, alias="OPENVPN_TCP_PORT")
    cloak_external_port: int = Field(default=443, alias="CLOAK_EXTERNAL_PORT")
    shadowsocks_public_port: int = Field(default=46768, alias="SHADOWSOCKS_PUBLIC_PORT")
    xray_restart_container: bool = Field(default=True, alias="XRAY_RESTART_CONTAINER")
    clean_xray_container: str = Field(
        default="vpn-clean-xray",
        alias="CLEAN_XRAY_CONTAINER",
    )
    clean_xray_host: str = Field(
        default="",
        alias="CLEAN_XRAY_HOST",
        description="Публичный хост для ссылок clean Xray (если пусто — PUBLIC_HOST/WG_ENDPOINT).",
    )
    clean_xray_port_vless: int = Field(default=7443, alias="CLEAN_XRAY_PORT_VLESS")
    clean_xray_port_trojan: int = Field(default=7444, alias="CLEAN_XRAY_PORT_TROJAN")
    clean_xray_port_vmess: int = Field(default=7445, alias="CLEAN_XRAY_PORT_VMESS")
    clean_xray_port_shadowsocks: int = Field(
        default=7446,
        alias="CLEAN_XRAY_PORT_SHADOWSOCKS",
    )
    clean_xray_api_port: int = Field(default=10085, alias="CLEAN_XRAY_API_PORT")
    clean_xray_reality_public_key: str = Field(
        default="",
        alias="CLEAN_XRAY_REALITY_PUBLIC_KEY",
    )
    clean_xray_reality_server_name: str = Field(
        default="www.cloudflare.com",
        alias="CLEAN_XRAY_REALITY_SERVER_NAME",
    )
    clean_xray_reality_short_id: str = Field(
        default="",
        alias="CLEAN_XRAY_REALITY_SHORT_ID",
    )
    clean_xray_ss_method: str = Field(
        default="chacha20-ietf-poly1305",
        alias="CLEAN_XRAY_SS_METHOD",
    )
    daemon_wg_interface: str = Field(default="awg0", alias="DAEMON_WG_INTERFACE")
    daemon_net_interface: str = Field(default="eth0", alias="DAEMON_NET_INTERFACE")
    bandwidth_guard_log: str = Field(
        default="/var/log/vpn_bot_bandwidth_guard.log",
        alias="BANDWIDTH_GUARD_LOG",
    )
    traffic_logger_log: str = Field(
        default="/var/log/vpn_bot_traffic_logger.log",
        alias="TRAFFIC_LOGGER_LOG",
    )
    stale_wg_key_days: int = Field(
        default=0,
        alias="STALE_WG_KEY_DAYS",
        description="0 — не удалять неактивные WG-ключи. ≥1 — удалять из БД ключи без awg-активности дольше N дней (и снимать peer на сервере).",
    )
    admin_backup_weekday: int = Field(
        default=0,
        alias="ADMIN_BACKUP_WEEKDAY",
        description="0=пн … 6=вс: в этот день в 08:00 МСК — напоминание админу сделать бэкап БД вручную (файл в Telegram не шлём).",
    )
    admin_journal_units: str = Field(
        default="vpn-bot.service,vpn-bot-traffic-logger.service,vpn-bot-bandwidth-guard.service",
        alias="ADMIN_JOURNAL_UNITS",
        description="systemd-юниты для подсчёта строк journalctl -p err за сутки отчёта.",
    )
    admin_alerts_enabled: bool = Field(
        default=True,
        alias="ADMIN_ALERTS_ENABLED",
        description="Включить скрипт admin_alerts (диск + рост ошибок journalctl).",
    )
    admin_alert_disk_warn_pct: int = Field(
        default=12,
        alias="ADMIN_ALERT_DISK_WARN_PCT",
        description="Предупреждение, если свободно меньше N% на диске /.",
    )
    admin_alert_disk_crit_pct: int = Field(
        default=7,
        alias="ADMIN_ALERT_DISK_CRIT_PCT",
        description="Критично, если свободно меньше N% на диске /.",
    )
    admin_alert_journal_window_min: int = Field(
        default=15,
        alias="ADMIN_ALERT_JOURNAL_WINDOW_MIN",
        description="Окно для подсчёта journalctl -p err (минуты).",
    )
    admin_alert_journal_abs: int = Field(
        default=80,
        alias="ADMIN_ALERT_JOURNAL_ABS",
        description="Уведомление, если за окно строк с ошибками не меньше этого числа.",
    )
    admin_alert_journal_growth_ratio: float = Field(
        default=2.0,
        alias="ADMIN_ALERT_JOURNAL_GROWTH_RATIO",
        description="Рост: текущее число >= предыдущее * ratio и >= growth_floor.",
    )
    admin_alert_journal_growth_floor: int = Field(
        default=20,
        alias="ADMIN_ALERT_JOURNAL_GROWTH_FLOOR",
        description="Минимум строк за окно, чтобы сработал критерий роста.",
    )
    admin_alert_cooldown_min: int = Field(
        default=60,
        alias="ADMIN_ALERT_COOLDOWN_MIN",
        description="Не чаще одного уведомления того же типа (минуты).",
    )

    @property
    def admin_journal_unit_list(self) -> list[str]:
        return [
            u.strip()
            for u in self.admin_journal_units.replace(" ", "").split(",")
            if u.strip()
        ]
    guides_src_dir: str = Field(
        default="Src",
        alias="GUIDES_SRC_DIR",
    )
    bot_avatar_online_path: str = Field(
        default=_DEFAULT_BOT_AVATAR_ONLINE,
        alias="BOT_AVATAR_ONLINE",
        description="PNG/JPEG: «бот на линии». Переопределите в .env при необходимости.",
    )
    bot_avatar_offline_path: str = Field(
        default=_DEFAULT_BOT_AVATAR_OFFLINE,
        alias="BOT_AVATAR_OFFLINE",
        description="PNG/JPEG: «на починке» (остановка сервиса).",
    )

    @field_validator("admin_ids_raw", mode="before")
    @classmethod
    def strip_admins(cls, v: str | None) -> str:
        if v is None:
            return ""
        return str(v).strip()

    @property
    def admin_ids(self) -> set[int]:
        if not self.admin_ids_raw:
            return set()
        out: set[int] = set()
        for part in self.admin_ids_raw.replace(" ", "").split(","):
            if not part:
                continue
            try:
                out.add(int(part))
            except ValueError:
                continue
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()
