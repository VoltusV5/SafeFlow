# Чек-лист Рефакторинга VPN-Бота (TDD & Clean Architecture)

> ВАЖНО: Весь код пишется строго по методологии TDD (Test-Driven Development). Сначала пишется тест (в папке `tests/`), проверяется, что он падает (Red), затем пишется реализация (Green), затем рефакторинг (Refactor).

## Этап 1: Инфраструктура и Конфигурация (DevOps Setup)
- `[ ]` Инициализация структуры директорий (`app`, `docs`, `smart_agent`, `tests`, `frontend`, `twa`).
- `[ ]` Создание `requirements.txt` (FastAPI, aiogram 3.x, sqlalchemy, asyncpg, alembic, redis, pydantic-settings, cryptography, pytest, pytest-asyncio, httpx).
- `[ ]` Создание `docker-compose.yml` (PostgreSQL, Redis, Бэкенд, Frontend).
- `[ ]` Настройка Pydantic Settings (`app/core/config.py`) и `.env.example`.
- `[ ]` TDD: Тесты шифрования Fernet -> Утилиты шифрования ключей (`app/core/security.py`).

## Этап 2: База Данных (Data Layer - Models)
- `[ ]` Настройка Async Engine и SessionMaker (`app/db/session.py`).
- `[ ]` Базовая модель SQLAlchemy (`app/db/models/base.py`).
- `[ ]` Создание моделей: `User`, `Subscription`, `Payment`, `Key`, `Server`, `Promocode`, `RefundTicket`.
- `[ ]` Инициализация Alembic (`alembic init -t async migrations`).
- `[ ]` Генерация и применение первой миграции БД.

## Этап 3: Доступ к Данным (Repositories & TDD)
- `[ ]` TDD: Тест Base CRUD -> Реализация `BaseRepository`.
- `[ ]` TDD: Тест UserRepository -> Реализация `UserRepository`.
- `[ ]` TDD: Тест SubscriptionRepository -> Реализация `SubscriptionRepository`.
- `[ ]` TDD: Тесты для Payment, Key, Server, Promocode Repositories -> Их реализация.

## Этап 4: Бизнес-логика (Service Layer & TDD)
- `[ ]` TDD: Тесты реферальных начислений и банов -> Реализация `UserService`.
- `[ ]` TDD: Тесты расчетов тарифов, применения промокодов и возвратов -> Реализация `BillingService`.
- `[ ]` TDD: Тесты аллокации IP/UUID и валидации серверов -> Реализация `VpnManagerService`.

## Этап 5: Фоновые задачи (Background Tasks)
- `[ ]` Настройка брокера задач (Redis + TaskIQ/Arq/APScheduler).
- `[ ]` Задача: Напоминание об истечении подписки (за 3 дня).
- `[ ]` Задача: Удаление ключей (Grace Period 24 часа после истечения).
- `[ ]` Задача: Reconciliation (синхронизация зависших `pending_sync` ключей).

## Этап 6: REST API Бэкенд (Transport Layer - FastAPI)
- `[ ]` Инициализация `FastAPI` (`app/main.py`) и инъекция сессий БД (Dependencies).
- `[ ]` Настройка **CORS Middleware** (Cross-Origin Resource Sharing) для связи с Frontend и TWA.
- `[ ]` TDD: Тесты эндпоинтов авторизации Telegram Login -> Эндпоинты Auth.
- `[ ]` TDD: Тесты обработки вебхуков (Payok/AAIO) -> Реализация `app/api/routes/payments.py`.
- `[ ]` TDD: Тесты эндпоинтов управления ключами -> Реализация REST API для Фронтенда.

## Этап 7: Telegram Бот (Команды и Кнопки)
- `[ ]` Инициализация Бота и Dispatcher с `RedisStorage` (`app/bot/main.py`).
- `[ ]` Middleware: Проверка `is_banned` и внедрение сессии БД.
- `[ ]` Базовые хендлеры: Команды `/start` (проверка триала), `/help`.
- `[ ]` Базовые хендлеры: Ветка кнопок (Inline / Reply) для навигации по меню.
- `[ ]` Хендлеры: `/subscribe`, `/my`, `/keys`, `/promo`.
- `[ ]` Хендлеры: `/admin` (баны, массовая перегенерация, тикеты).

## Этап 8: Telegram Web App (TWA Frontend)
- `[ ]` Инициализация Frontend проекта (React/Vue/HTML+JS) в папке `twa/`.
- `[ ]` Настройка связи с `Telegram.WebApp` API (получение `initData` пользователя).
- `[ ]` Верстка красивого UI: Дашборд пользователя, Кнопка "Оплатить", Список ключей.
- `[ ]` Интеграция с REST API FastAPI: генерация ключей и отображение конфигов.

## Этап 9: Standalone WEB-Сайт (Внешний Личный Кабинет)
- `[ ]` Инициализация Frontend проекта (React/Next.js/Vue) в папке `frontend/`.
- `[ ]` Настройка Telegram OAuth (Вход через Telegram) для авторизации вне мессенджера.
- `[ ]` Реализация страниц: Тарифы, Личный профиль, Управление ключами, Инструкции по установке.
- `[ ]` Интеграция с REST API FastAPI.

## Этап 10: Smart Agent (Рабочие ноды)
- `[ ]` Инициализация легковесного FastAPI приложения для агента (`smart_agent/main.py`).
- `[ ]` Защита эндпоинтов (Static Bearer Token + IP Whitelist).
- `[ ]` TDD: Тесты конфигураторов -> Логика генерации `wg0.conf` и `config.json` (Xray).
- `[ ]` Интеграция с локальными сервисами (перезапуск systemd/docker контейнеров WG/Xray).

## Этап 11: Инфраструктура и Деплой (DevOps)
- `[ ]` Настройка Nginx/Caddy для проксирования FastAPI, TWA и WEB-сайта.
- `[ ]` Сборка финальных Docker-образов (Backend, Agent, Frontend).
- `[ ]` Настройка CI/CD пайплайна (GitHub Actions).
- `[ ]` Подготовка финальной документации MkDocs.