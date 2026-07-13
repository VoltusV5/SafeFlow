# Чек-лист Рефакторинга VPN-Бота (TDD & Clean Architecture)

> ВАЖНО: Весь код пишется строго по методологии TDD (Test-Driven Development). Сначала пишется тест (в папке `tests/`), проверяется, что он падает (Red), затем пишется реализация (Green), затем рефакторинг (Refactor).

## Этап 1: Инфраструктура и Конфигурация (DevOps Setup)
- `[x]` Инициализация структуры директорий (`app`, `docs`, `smart_agent`, `tests`, `frontend`, `twa`).
- `[x]` Создание `requirements.txt` (FastAPI, aiogram 3.x, sqlalchemy, asyncpg, alembic, redis, pydantic-settings, cryptography, pytest, pytest-asyncio, httpx).
- `[x]` Создание `docker-compose.yml` (PostgreSQL, Redis, Бэкенд, Frontend).
- `[x]` Настройка Pydantic Settings (`app/core/config.py`) и `.env.example`.
- `[x]` TDD: Тесты шифрования Fernet -> Утилиты шифрования ключей (`app/core/security.py`).

```text
vpn-telegram-bot/
├── app/
│   ├── api/                 # FastAPI роутеры (эндпоинты REST)
│   │   ├── dependencies.py
│   │   └── routes/
│   ├── bot/                 # Хендлеры aiogram (интерфейс Telegram)
│   │   ├── handlers/
│   │   ├── keyboards/
│   │   └── middlewares/
│   ├── core/                # Конфигурация (Pydantic settings, логирование)
│   │   ├── config.py
│   │   └── security.py
│   ├── db/                  # База данных
│   │   ├── migrations/      # Alembic миграции
│   │   ├── models/          # SQLAlchemy модели таблиц
│   │   └── repositories/    # Паттерн Repository для изоляции SQL
│   ├── services/            # Бизнес-логика (не зависит от API или Бота)
│   │   ├── billing.py
│   │   ├── vpn_manager.py
│   │   └── users.py
│   ├── tasks/               # Фоновые джобы (Redis/Celery/arq)
│   └── main.py              # Точка входа (Инициализация FastAPI и Бота)
├── docs/                    # Документация (MkDocs)
│   ├── schema.dbml
│   └── план рефактора.md
├── smart_agent/             # Код легковесного агента для нод (FastAPI)
│   ├── main.py
│   └── vpn_builder.py
├── tests/                   # Автотесты (pytest)
├── .github/workflows/       # CI/CD пайплайны
├── docker-compose.yml       # Инфраструктура центрального сервера
└── requirements.txt         # Зависимости Python
```

## Этап 2: База Данных (Data Layer - Models)
- `[x]` Настройка Async Engine и SessionMaker (`app/db/session.py`).
- `[x]` Базовая модель SQLAlchemy (`app/db/models/base.py`).
- `[x]` Создание моделей: `User`, `Subscription`, `Payment`, `Key`, `Server`, `Promocode`, `RefundTicket`.
- `[x]` Инициализация Alembic (`alembic init -t async migrations`).
- `[x]` Генерация и применение первой миграции БД.

## Этап 3: Доступ к Данным (Repositories & TDD)
- `[x]` TDD: Тест Base CRUD -> Реализация `BaseRepository`.
- `[x]` TDD: Тест UserRepository -> Реализация `UserRepository`.
- `[x]` TDD: Тест SubscriptionRepository -> Реализация `SubscriptionRepository`.
- `[x]` TDD: Тесты для Payment, Key, Server, Promocode Repositories -> Их реализация.

## Этап 4: Архитектура (UoW, DTO, Enums) и Бизнес-логика (Service Layer)
- `[x]` Архитектура: Реализация паттерна Unit Of Work (`app/db/uow.py`) и удаление жестких `await self.session.commit()` из методов репозиториев для обеспечения консистентности транзакций.
- `[x]` Архитектура: Создание Pydantic схем (DTO) для обмена данными (`app/schemas/`).
- `[x]` Архитектура: Замена строковых типов на ENUM в моделях БД и применение миграции.
- `[x]` TDD: Тесты реферальных начислений и банов -> Реализация `UserService`.
- `[x]` TDD: Тесты расчетов тарифов, применения промокодов и возвратов -> Реализация `BillingService`.
- `[x]` TDD: Тесты аллокации IP/UUID и валидации серверов -> Реализация `VpnManagerService`.

## Этап 5: Фоновые задачи и Мультиавторизация
- `[x]` БД: Миграция `User` (поля `email`, `hashed_password`, `notification_preference`, `tg_id` nullable).
- `[x]` Архитектура: Паттерн "Стратегия" для уведомлений (Интерфейс + Telegram + Email).
- `[x]` Настройка брокера задач (Redis + `arq` worker).
- `[x]` Задача: Напоминание об истечении подписки (за 3 дня) через Стратегию.
- `[x]` Задача: Удаление ключей (Grace Period 24 часа после истечения).
- `[x]` Задача: Reconciliation (синхронизация зависших `pending_sync` ключей).

## Этап 6: REST API Бэкенд (Transport Layer - FastAPI)
- `[x]` Инициализация `FastAPI` (`app/main.py`) и инъекция сессий БД (Dependencies).
- `[x]` Настройка **CORS Middleware** (Cross-Origin Resource Sharing) для связи с Frontend и TWA.
- `[x]` TDD: Тесты эндпоинтов авторизации Telegram Login -> Эндпоинты Auth.
- `[x]` TDD: Тесты обработки вебхуков (AAIO) -> Реализация `app/api/routes/payments.py`.
- `[x]` TDD: Тесты эндпоинтов управления ключами -> Реализация REST API для Фронтенда.

## Этап 7: Telegram Бот (Команды и Кнопки)
- `[x]` Инициализация Бота и Dispatcher с `RedisStorage` (`app/bot/main.py`).
- `[x]` Middleware: Проверка `is_banned` и внедрение сессии БД.
- `[x]` Базовые хендлеры: Команды `/start` (проверка триала), `/help`.
- `[x]` Базовые хендлеры: Ветка кнопок (Inline / Reply) для навигации по меню.
- `[ ]` Доработка интерфейса: текстовые команды `/subscribe`, `/my` (профиль), `/keys` (список), `/promo`.
- `[ ]` Админ-панель: `/admin` (баны, массовая перегенерация, тикеты, статистика).

## Этап 8: Telegram Web App (TWA Frontend)
- `[x]` Инициализация Frontend проекта (React/Vue/HTML+JS) в папке `twa/` (или `frontend/`).
- `[x]` Настройка связи с `Telegram.WebApp` API (получение `initData` пользователя).
- `[x]` Верстка красивого UI: Дашборд пользователя, Кнопка "Оплатить", Список ключей.
- `[x]` Интеграция с REST API FastAPI: генерация ключей и отображение конфигов.

## Этап 9: Standalone WEB-Сайт (Внешний Личный Кабинет)
- `[x]` Инициализация Frontend проекта (Vue 3) в папке `frontend/`.
- `[x]` Настройка входа через Email/Код/Пароль для авторизации вне мессенджера (Вместо Telegram OAuth).
- `[x]` Реализация страниц: Авторизация, Личный профиль, Тарифы, Управление ключами.
- `[x]` Интеграция с REST API FastAPI (включая Rate Limits и CORS).

## Этап 10: Smart Agent (Рабочие ноды)
- `[x]` Инициализация легковесного FastAPI приложения для агента (`smart_agent/main.py`).
- `[x]` Защита эндпоинтов (Static Bearer Token + IP Whitelist).
- `[x]` TDD: Тесты конфигураторов -> Логика генерации `wg0.conf` и `config.json` (Xray).
- `[x]` Интеграция с сервисами VPN (AmneziaWG, Xray).

## Этап 11: Инфраструктура и Деплой (DevOps)
- `[x]` Настройка Nginx для проксирования FastAPI и Frontend (CORS решен).
- `[ ]` Интеграция боевой платежной системы (ЮKassa / CryptoBot / AAIO) вместо песочницы.
- `[ ]` Сборка финальных Docker-образов (Backend, Agent, Frontend).
- `[ ]` Настройка CI/CD пайплайна (GitHub Actions).
- `[ ]` Подготовка финальной документации MkDocs.