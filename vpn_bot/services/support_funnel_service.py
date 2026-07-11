"""Логирование и агрегаты воронки «Поддержать» для админ-дайджеста."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vpn_bot.db.models import (
    DonationAlertsSubscription,
    StarDonationSubscription,
    StarPayment,
    SupportFunnelEvent,
)

logger = logging.getLogger(__name__)


class SupportFunnelKind:
    OPEN = "support_open"
    MENU = "donate_menu"
    DA = "donate_da"
    DA_ONCE = "donate_da_once"
    DA_MONTHLY = "donate_da_monthly"
    TR = "donate_tr"
    TR_LINKS = "donate_tr_links"
    TR_EMPTY = "donate_tr_empty"
    ST = "donate_st"
    ST_AMOUNT = "donate_st_amount"
    ST_INV_ONCE = "donate_st_inv_once"
    ST_INV_MONTHLY = "donate_st_inv_monthly"
    ST_REMINDER_INV = "donate_st_reminder_inv"
    DA_REM_OFF = "donate_da_rem_off"
    ST_REM_OFF = "donate_st_rem_off"


async def log_support_funnel_event(
    session: AsyncSession,
    user_id: int,
    kind: str,
) -> None:
    try:
        session.add(SupportFunnelEvent(user_id=user_id, event=kind))
    except Exception:
        logger.exception("log_support_funnel_event failed kind=%s user=%s", kind, user_id)


async def _counts_by_event(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[str, tuple[int, int]]:
    """event -> (всего нажатий, уникальных пользователей)."""
    uid = SupportFunnelEvent.user_id
    r = await session.execute(
        select(
            SupportFunnelEvent.event,
            func.count().label("n"),
            func.count(func.distinct(uid)).label("nu"),
        ).where(
            SupportFunnelEvent.created_at >= start,
            SupportFunnelEvent.created_at < end,
        )
        .group_by(SupportFunnelEvent.event)
    )
    return {str(row[0]): (int(row[1]), int(row[2])) for row in r.all()}


async def support_funnel_digest_lines(
    session: AsyncSession, start: datetime, end: datetime
) -> list[str]:
    by = await _counts_by_event(session, start, end)

    def c(kind: str) -> tuple[int, int]:
        return by.get(kind, (0, 0))

    o_n, o_u = c(SupportFunnelKind.OPEN)
    inner_total = sum(
        n for k, (n, _) in by.items() if k != SupportFunnelKind.OPEN
    )

    lines = [
        "",
        "Поддержка проекта (воронка в бота):",
        f"  • открыли «Поддержать» (кнопка или /donate): {o_n} раз, уникальных пользователей: {o_u}",
        f"  • всего внутренних действий (inline и шаги ниже, без первого открытия): {inner_total}",
        "  • по шагам (раз / уникальных):",
        f"    — назад к способам оплаты: {c(SupportFunnelKind.MENU)[0]} / {c(SupportFunnelKind.MENU)[1]}",
        f"    — выбрали Donation Alerts: {c(SupportFunnelKind.DA)[0]} / {c(SupportFunnelKind.DA)[1]}",
        f"    — DA разово (экран со ссылкой): {c(SupportFunnelKind.DA_ONCE)[0]} / {c(SupportFunnelKind.DA_ONCE)[1]}",
        f"    — DA ежемесячно (+ экран со ссылкой): {c(SupportFunnelKind.DA_MONTHLY)[0]} / {c(SupportFunnelKind.DA_MONTHLY)[1]}",
        f"    — выбрали Tribute: {c(SupportFunnelKind.TR)[0]} / {c(SupportFunnelKind.TR)[1]}",
        f"    — Tribute — показаны ссылки веб/Telegram: {c(SupportFunnelKind.TR_LINKS)[0]} / {c(SupportFunnelKind.TR_LINKS)[1]}",
        f"    — Tribute — ссылки не заданы: {c(SupportFunnelKind.TR_EMPTY)[0]} / {c(SupportFunnelKind.TR_EMPTY)[1]}",
        f"    — звёзды — открыли ввод суммы: {c(SupportFunnelKind.ST)[0]} / {c(SupportFunnelKind.ST)[1]}",
        f"    — звёзды — ввели допустимую сумму: {c(SupportFunnelKind.ST_AMOUNT)[0]} / {c(SupportFunnelKind.ST_AMOUNT)[1]}",
        f"    — звёзды — выставлен счёт (разово): {c(SupportFunnelKind.ST_INV_ONCE)[0]} / {c(SupportFunnelKind.ST_INV_ONCE)[1]}",
        f"    — звёзды — выставлен счёт (ежемесячно): {c(SupportFunnelKind.ST_INV_MONTHLY)[0]} / {c(SupportFunnelKind.ST_INV_MONTHLY)[1]}",
        f"    — звёзды — счёт из напоминания: {c(SupportFunnelKind.ST_REMINDER_INV)[0]} / {c(SupportFunnelKind.ST_REMINDER_INV)[1]}",
        f"    — отключили напоминание DA: {c(SupportFunnelKind.DA_REM_OFF)[0]} / {c(SupportFunnelKind.DA_REM_OFF)[1]}",
        f"    — отключили напоминание звёзд: {c(SupportFunnelKind.ST_REM_OFF)[0]} / {c(SupportFunnelKind.ST_REM_OFF)[1]}",
        "  • внешние переходы по url-кнопкам Telegram не присылает в бот — ориентир: "
        "строки «DA … экран со ссылкой» и «Tribute — показаны ссылки».",
    ]

    sp = await session.execute(
        select(
            func.count(),
            func.coalesce(func.sum(StarPayment.stars_amount), 0),
            func.count(func.distinct(StarPayment.user_id)),
        ).where(
            StarPayment.created_at >= start,
            StarPayment.created_at < end,
        )
    )
    pay_n, stars_sum, pay_u = sp.one()
    pay_n = int(pay_n or 0)
    stars_sum = int(stars_sum or 0)
    pay_u = int(pay_u or 0)

    lines.extend(
        [
            "  • оплаты звёздами (успешные платежи в боте, БД star_payments):",
            f"    — платежей: {pay_n}, уникальных плательщиков: {pay_u}, всего звёзд: {stars_sum} ⭐",
        ]
    )

    da_sub = await session.scalar(
        select(func.count())
        .select_from(DonationAlertsSubscription)
        .where(
            DonationAlertsSubscription.created_at >= start,
            DonationAlertsSubscription.created_at < end,
        )
    )
    st_sub = await session.scalar(
        select(func.count())
        .select_from(StarDonationSubscription)
        .where(
            StarDonationSubscription.created_at >= start,
            StarDonationSubscription.created_at < end,
        )
    )
    lines.extend(
        [
            f"  • оформили ежемесячное напоминание Donation Alerts: {int(da_sub or 0)}",
            f"  • оформили ежемесячную подписку на звёзды (напоминания): {int(st_sub or 0)}",
        ]
    )

    return lines
