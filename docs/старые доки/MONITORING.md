# Мониторинг — простыми словами

**Что это:** скрипт проверяет **три systemd-сервиса бота**, что **основные Docker-контейнеры** (Amnezia + Telegram-прокси) в состоянии `running`, и **целостность двух SQLite**. Это не «облачный мониторинг» и не дашборд — это быстрая самопроверка на самом сервере.

**Как пользоваться (чаще всего достаточно этого):**

```bash
/root/vpn-telegram-bot/venv/bin/python /root/vpn-telegram-bot/scripts/vpn_bot_healthcheck.py
```

- Если в ответ **`OK`** — юниты в `active`, контейнеры в `running`, целостность обеих БД в порядке.
- Если ошибки — в stderr будет текст (юнит, контейнер или БД).

Скрипт сам подставляет корень проекта в `PYTHONPATH` и переходит в каталог проекта, чтобы прочитать `.env` — **запускать можно из любой папки** (путь к `python` и к скрипту лучше указывать полностью, как выше).

**Опции:**

- `--skip-systemd` — не проверять `systemctl` (например на ПК без ваших юнитов).
- `--skip-docker` — не проверять Docker-контейнеры (dev или без Docker).
- `--notify-admins` — при любой ошибке **отправить сообщение в Telegram** всем из **`ADMIN_IDS`** тем же ботом (`BOT_TOKEN`). Удобно в связке с systemd (см. ниже).
- Переменная `VPN_BOT_HEALTHCHECK_UNITS` — свой список юнитов через запятую.
- Переменная `VPN_BOT_HEALTHCHECK_CONTAINERS` — список имён контейнеров через запятую (по умолчанию Amnezia + `vpn-telegram-*`). Если меняете состав VPN — уточните список в `.env`.

**Автоматически раз в 10 минут (на сервере):** установлены `vpn-bot-healthcheck.timer` + `vpn-bot-healthcheck.service` (файлы в `deploy/`). Сервис запускает скрипт **с `--notify-admins`**: при сбое админы получают текст ошибки в Telegram; при успехе в журнал пишется `OK`, в Telegram ничего не шлётся.

Убедитесь, что в `.env` заданы **`BOT_TOKEN`** и непустой **`ADMIN_IDS`** (через запятую, числовые id).

**Файл аналитики `vpn_bot_analytics.db`:** если его ещё нет, создайте перезапуском бота (`systemctl restart vpn-bot`) или вручную через `init_analytics_db`. Пока файла нет, healthcheck считается неуспешным и при `--notify-admins` уйдёт уведомление.

---

## Две базы данных (зачем)

| Файл / URL | Содержимое |
|------------|------------|
| Основная (`DATABASE_URL`) | Пользователи, ключи, донаты, лимиты |
| Аналитика (`ANALYTICS_DATABASE_URL`) | Трафик (`traffic_log`), метрики хоста, `daily_stats` |

Пример в `.env`:

```env
DATABASE_URL=sqlite+aiosqlite:////opt/vpn/bot_data.db
ANALYTICS_DATABASE_URL=sqlite+aiosqlite:////opt/vpn/vpn_bot_analytics.db
```

**Перенос старых таблиц** из одной БД в аналитику (один раз, с бэкапом файлов):

```bash
cd /root/vpn-telegram-bot
./venv/bin/python scripts/migrate_analytics_from_main.py
```

Удаление старых таблиц из основной БД **только** после проверки копии:

```bash
./venv/bin/python scripts/migrate_analytics_from_main.py --drop-main-tables
```

---

## Systemd: таймер раз в 10 минут + Telegram при ошибке

Готовые unit-файлы лежат в репозитории:

- `deploy/vpn-bot-healthcheck.service` — `ExecStart=... vpn_bot_healthcheck.py --notify-admins`
- `deploy/vpn-bot-healthcheck.timer` — `OnUnitActiveSec=10min`

Установка / обновление:

```bash
sudo cp deploy/vpn-bot-healthcheck.service deploy/vpn-bot-healthcheck.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-bot-healthcheck.timer
```

Проверка: `systemctl list-timers vpn-bot-healthcheck.timer`, логи: `journalctl -u vpn-bot-healthcheck.service`.

---

## Алерты админу: диск и ошибки journalctl

Отдельно от healthcheck: скрипт `scripts/admin_alerts.py` проверяет:

- **свободное место на `/`** — предупреждение и критический порог (по умолчанию ~12% и ~7% свободно);
- **рост ошибок** `journalctl -p err` по юнитам из **`ADMIN_JOURNAL_UNITS`** за скользящее окно (по умолчанию 15 минут): срабатывание при большом числе строк за окно **или** при резком росте относительно прошлого замера (состояние в файле `.admin_alerts_state.json` в корне проекта).

Падение **systemd** / **Docker** / **SQLite** по-прежнему ловит **`vpn_bot_healthcheck.py`** (таймер раз в 10 минут). Алерты дополняют его диском и журналом.

Установка таймера (раз в 15 минут):

```bash
sudo cp /root/vpn-telegram-bot/deploy/vpn-bot-admin-alerts.service /root/vpn-telegram-bot/deploy/vpn-bot-admin-alerts.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vpn-bot-admin-alerts.timer
```

Проверка: `systemctl list-timers vpn-bot-admin-alerts.timer`, ручной запуск: `systemctl start vpn-bot-admin-alerts.service`.

Пороги задаются в `.env` (см. `.env.example`, префикс `ADMIN_ALERT_*`). Отключить: `ADMIN_ALERTS_ENABLED=false`.

---

## Что ещё смотреть вручную

- Логи бота и демонов: `journalctl -u vpn-bot.service -f` и т.д.
- Контейнеры Amnezia: `docker ps` (ожидается `Up`).
- Логи из `.env`: `TRAFFIC_LOGGER_LOG`, `BANDWIDTH_GUARD_LOG`.
- Ежедневный дайджест админам (если заданы `ADMIN_IDS`), в т.ч. ошибки `journalctl` по `ADMIN_JOURNAL_UNITS`; в блоке «Ключи» — число **WG-ключей с handshake за последние 24 ч** (снимок `wg`).
- Автоудаление давно неактивных WG-ключей из БД: **`STALE_WG_KEY_DAYS=0`** в `.env` — не удалять (по умолчанию в коде тоже 0). Значение `≥1` включает ежедневную очистку.
- Бэкап: в еженедельном напоминании от `traffic_logger` указываются пути к обоим файлам SQLite, если они найдены на диске.

---

## Прокси для Telegram (MTProto + SOCKS5)

Поднимается отдельным compose-файлом (образы `ghcr.io/9seconds/mtg`, `serjs/go-socks5-proxy`, `ginuerzh/gost`). В `.env` задаются `TELEGRAM_MTPROTO_SECRET` (рекомендуется **fake TLS**: `mtg generate-secret www.cloudflare.com` или свой домен), `TELEGRAM_SOCKS_*`, `TELEGRAM_HTTP_PROXY_*` и при необходимости порты. **Браузерный HTTP-прокси** и **SOCKS5** не зависят от секрета MTProto.

```bash
cd /root/vpn-telegram-bot
docker compose -f deploy/docker-compose.telegram-proxy.yml --env-file .env up -d
```

Проверка: `docker ps` — контейнеры `vpn-telegram-mtg`, `vpn-telegram-socks5` и `vpn-telegram-http-proxy` в статусе `Up`. После смены секретов в `.env` — `docker compose ... up -d --force-recreate` и `systemctl restart vpn-bot`, чтобы бот показывал актуальные данные.

У **Docker Compose** переменные из **текущей оболочки** имеют приоритет над `--env-file`. Если в сессии был `export TELEGRAM_HTTP_PROXY_PORT=…` (или другой `TELEGRAM_*_PORT`), подставится он, а не строка из `.env`. Перед `up` сделайте `unset TELEGRAM_HTTP_PROXY_PORT TELEGRAM_SOCKS_PORT TELEGRAM_MTPROTO_PORT` или явно подставьте нужные значения в командной строке.

Если на сервере включён `ufw`, откройте TCP-порты из `.env`: MTProto (**8888** + альтернативы **8443**, **2053**), SOCKS5 (**64945** + **64946**, **64947**), HTTP для расширений (**8086**).

### AmneziaWG «вечное подключение», а OpenVPN/Xray работают

Иногда в контейнере **`amnezia-awg`** интерфейс **`wg0` не поднят** (ошибка при старте, рестарт без успешного `wg-quick up`), при этом контейнер числится `Up`. Проверка:

```bash
docker exec amnezia-awg ip link show wg0
```

Если «Device does not exist» — перезапуск: `docker restart amnezia-awg`, затем снова проверить `wg0`. После рестарта клиенты AmneziaWG должны снова проходить handshake на UDP **41241**.

### Два Amnezia AWG (legacy + новые ключи) и остальные протоколы

Чтобы **старые Amnezia WG** не ломать, новые ключи можно выдавать из **второго контейнера** (`amnezia-awg-20`, другой UDP-порт и подсеть `10.8.2.x` в `.env`: `AWG2_*`, `WG2_*`). Контейнеры **amnezia-xray**, **amnezia-openvpn-cloak**, **amnezia-openvpn**, **amnezia-wireguard**, **amnezia-ipsec**, **amnezia-shadowsocks** с этим не пересоздаются: их ключи в БД бота остаются на те же `vpn://` и те же контейнеры.

Перед любыми экспериментами с Docker на VPS: **`bash scripts/backup_amnezia_stack.sh`** — снимет `docker inspect` и архивы конфигов в `/root/backups/amnezia-stack-…` (без остановки сервисов).

### MTProto: на ПК работает, в телефоне «недоступен»

Чаще всего **мобильный оператор режет или не пускает TCP-порт прокси**. Если снова «недоступен» — пробуйте **полный VPN** (Amnezia), смену порта в `.env` + `docker compose ... --force-recreate`, или высокий порт для SOCKS (как **64945**).
