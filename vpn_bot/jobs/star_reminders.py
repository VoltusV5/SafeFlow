from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from vpn_bot.config import get_settings
from vpn_bot.db.session import session_scope
from vpn_bot.keyboards import da_monthly_reminder_kb, star_monthly_reminder_kb
from vpn_bot.services.da_reminder_service import DonationAlertsReminderService
from vpn_bot.services.star_donation_service import StarDonationService
from vpn_bot.utils.donate_payload import da_reminder_text, reminder_text

logger = logging.getLogger(__name__)

# Один раз в сутки: выбираем всех, у кого next_reminder_at уже наступил (звёзды и DA).
# После успешной отправки bump_reminder сдвигает дату на +30 дней → не чаще 1 сообщения в месяц на канал.
_REMINDER_TICK_SEC = 86400


async def monthly_donation_reminders_loop(bot: Bot) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            await _process_due(bot)
            await _process_da_due(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("monthly_donation_reminders_loop tick failed")
        await asyncio.sleep(_REMINDER_TICK_SEC)


async def _process_due(bot: Bot) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    async with session_scope() as session:
        due = await StarDonationService(session).list_due(now)
    for sub_id, tg_id, stars in due:
        try:
            await bot.send_message(
                int(tg_id),
                reminder_text(stars),
                reply_markup=star_monthly_reminder_kb(stars),
            )
        except TelegramBadRequest as e:
            logger.warning("star reminder to tg_id=%s: %s", tg_id, e)
            continue
        async with session_scope() as session:
            await StarDonationService(session).bump_reminder(sub_id)


async def _process_da_due(bot: Bot) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    url = get_settings().donation_alerts_url.strip() or "https://www.donationalerts.com/"
    async with session_scope() as session:
        due = await DonationAlertsReminderService(session).list_due(now)
    for sub_id, tg_id in due:
        try:
            await bot.send_message(
                int(tg_id),
                da_reminder_text(),
                reply_markup=da_monthly_reminder_kb(url),
            )
        except TelegramBadRequest as e:
            logger.warning("DA reminder to tg_id=%s: %s", tg_id, e)
            continue
        async with session_scope() as session:
            await DonationAlertsReminderService(session).bump_reminder(sub_id)
