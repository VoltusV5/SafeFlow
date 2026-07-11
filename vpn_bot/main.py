from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from vpn_bot.config import get_settings
from vpn_bot.db.session import init_db
from vpn_bot.db.session_analytics import init_analytics_db
from vpn_bot.handlers import (
    admin,
    browser_extension,
    common,
    contact_admin,
    donate,
    guest,
    member,
    report_problem,
    telegram_proxy,
)
from vpn_bot.jobs.star_reminders import monthly_donation_reminders_loop
from vpn_bot.middlewares import AuthMiddleware, BanMiddleware, DbSessionMiddleware


async def run_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    await init_db()
    await init_analytics_db()
    settings = get_settings()
    bot = Bot(settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(AuthMiddleware())
    dp.update.middleware(BanMiddleware())
    dp.include_router(admin.router)
    dp.include_router(contact_admin.router)
    dp.include_router(report_problem.router)
    dp.include_router(common.router)
    dp.include_router(donate.router)
    dp.include_router(member.router)
    dp.include_router(telegram_proxy.router)
    dp.include_router(browser_extension.router)
    dp.include_router(guest.router)

    @dp.startup()
    async def _on_startup(bot: Bot) -> None:
        asyncio.create_task(monthly_donation_reminders_loop(bot))

    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
