from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter, and_f
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from vpn_bot.config import get_settings
from vpn_bot.constants import (
    MAIN_MENU_BUTTON_BACK_TO_MAIN,
    MAX_TELEGRAM_STARS_DONATION,
    MIN_TELEGRAM_STARS_DONATION,
)
from vpn_bot.db.models import User
from vpn_bot.filters import AuthedFilter
from vpn_bot.handlers.contact_admin import ContactStates
from vpn_bot.handlers.report_problem import ReportProblemStates
from vpn_bot.keyboards import (
    da_freq_kb,
    donate_back_kb,  # noqa: F401, E501
    donate_methods_kb,
    main_menu_kb,
    star_freq_kb,
    star_monthly_reminder_kb,
    tribute_links_kb,
)
from vpn_bot.services.da_reminder_service import DonationAlertsReminderService
from vpn_bot.services.star_donation_service import StarDonationService
from vpn_bot.utils.donate_payload import (
    build_star_invoice_payload,
    parse_star_invoice_payload,
)

logger = logging.getLogger(__name__)

router = Router(name="donate")
_auth = AuthedFilter()
_not_in_contact = and_f(
    ~StateFilter(ContactStates.composing),
    ~StateFilter(ReportProblemStates.waiting_other),
)

_STAR_AMOUNT_KEY = "donate_stars"

DONATE_INTRO = (
    "Поддержать проект:\n\n"
    "• Donation Alerts (от 10 ₽, СБП, МИР) — разово или с напоминанием раз в месяц.\n"  # noqa: E501
    "• Tribute (от 100 ₽, СБП, МИР) — разово или подписка на стороне сервиса.\n"  # noqa: E501
    "• Звёзды Telegram (СБП, МИР) — сумму вводите вы; можно разово или с ежемесячным напоминанием.\n\n"  # noqa: E501
    "Выберите способ:"
)

TEXT_DA = (
    "Donation Alerts (от 10 ₽, СБП, МИР).\n"
    "Разово: сразу перейдёте на страницу оплаты.\n"
    "Ежемесячно: через месяц пришлём напоминание со ссылкой на Donation Alerts "  # noqa: E501
    "(оплата по-прежнему на сайте; бот только напоминает).\n\n"
    "Выберите вариант:"
)

TEXT_TR = (
    "Tribute (от 100 ₽, СБП, МИР).\nНа странице Tribute можно выбрать разовый платёж "  # noqa: E501
    "или ежемесячную поддержку.\n\n"
    "Откройте удобный вариант:"
)


class DonateStates(StatesGroup):
    waiting_star_amount = State()


def _invoice_texts(stars: int, monthly: bool) -> tuple[str, str]:
    title = "Поддержка проекта"
    if monthly:
        desc = (
            f"{stars} ⭐. После оплаты раз в месяц пришлём напоминание снова отправить "  # noqa: E501
            f"ту же сумму."
        )
    else:
        desc = f"{stars} ⭐ — разовая поддержка."
    return title, desc


async def _send_star_invoice(
    bot,
    chat_id: int,
    stars: int,
    monthly: bool,
) -> None:
    payload = build_star_invoice_payload(monthly, stars)
    if len(payload.encode("utf-8")) > 128:
        raise ValueError("payload too long")
    title, description = _invoice_texts(stars, monthly)
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label="XTR", amount=stars)],
        provider_token="",
    )


@router.pre_checkout_query()
async def pre_checkout_star(query: PreCheckoutQuery) -> None:
    parsed = parse_star_invoice_payload(query.invoice_payload)
    if query.currency != "XTR" or parsed is None:
        await query.answer(ok=False, error_message="Счёт недействителен.")
        return
    _monthly, stars = parsed
    if query.total_amount != stars:
        await query.answer(ok=False, error_message="Сумма не совпадает.")
        return
    await query.answer(ok=True)


@router.message(_auth, F.successful_payment)
async def on_successful_payment(
    message: Message, session, db_user: User | None
) -> None:  # noqa: E501
    sp = message.successful_payment
    if not sp:
        return
    if sp.currency != "XTR":
        return
    parsed = parse_star_invoice_payload(sp.invoice_payload)
    if parsed is None or sp.total_amount != parsed[1]:
        logger.warning(
            "ignored payment payload mismatch from tg_id=%s", message.from_user.id
        )  # noqa: E501
        return
    monthly, stars = parsed
    if db_user is None:
        return
    svc = StarDonationService(session)
    if not await svc.record_star_payment(
        db_user.id,
        stars,
        monthly,
        sp.telegram_payment_charge_id,
    ):
        return
    if monthly:
        await svc.upsert_monthly(db_user.id, stars)
        await message.answer(
            "Спасибо! Вы выбрали ежемесячную поддержку звёздами: через месяц предложим "  # noqa: E501
            f"снова отправить {stars} ⭐.\n\n"
            "Отключить напоминания: /stars_remind_off",
            reply_markup=main_menu_kb(),
        )
    else:
        await message.answer(
            "Спасибо за поддержку!",
            reply_markup=main_menu_kb(),
        )


@router.message(_auth, Command("stars_remind_off"))
async def cmd_stars_remind_off(
    message: Message, db_user: User, session
) -> None:  # noqa: E501
    ok = await StarDonationService(session).deactivate_for_user(db_user.id)
    if ok:
        await message.answer("Ежемесячные напоминания о звёздах отключены.")
    else:
        await message.answer("Активной подписки с напоминаниями не найдено.")


@router.message(_auth, Command("da_remind_off"))
async def cmd_da_remind_off(message: Message, db_user: User, session) -> None:
    ok = await DonationAlertsReminderService(session).deactivate_for_user(
        db_user.id
    )  # noqa: E501
    if ok:
        await message.answer(
            "Ежемесячные напоминания о Donation Alerts отключены."
        )  # noqa: E501
    else:
        await message.answer(
            "Активного напоминания Donation Alerts не найдено."
        )  # noqa: E501


@router.message(_auth, _not_in_contact, F.text == "Поддержать")
@router.message(_auth, _not_in_contact, Command("donate"))
async def donate_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        DONATE_INTRO,
        reply_markup=donate_methods_kb(),
    )


@router.callback_query(_auth, F.data == "donate:menu")
async def donate_menu(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            DONATE_INTRO, reply_markup=donate_methods_kb()
        )  # noqa: E501
    await cb.answer()


@router.callback_query(_auth, F.data == "donate:da")
async def donate_da(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(TEXT_DA, reply_markup=da_freq_kb())
    await cb.answer()


@router.callback_query(_auth, F.data == "donate:da:o")
async def donate_da_once(cb: CallbackQuery) -> None:
    url = (
        get_settings().donation_alerts_url.strip() or "https://www.donationalerts.com/"
    )  # noqa: E501
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Donation Alerts — оплатить", url=url)],
            [
                InlineKeyboardButton(
                    text="К способам оплаты",
                    callback_data="donate:menu",
                )
            ],
        ]
    )
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Donation Alerts — разовая поддержка.\n"
            "Нажмите кнопку и завершите оплату на сайте.",
            reply_markup=kb,
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "donate:da:m")
async def donate_da_monthly(cb: CallbackQuery, db_user: User, session) -> None:
    await DonationAlertsReminderService(session).upsert_monthly(db_user.id)
    url = (
        get_settings().donation_alerts_url.strip() or "https://www.donationalerts.com/"
    )  # noqa: E501
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Donation Alerts — оплатить", url=url)],
            [
                InlineKeyboardButton(
                    text="К способам оплаты",
                    callback_data="donate:menu",
                )
            ],
        ]
    )
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Готово: раз в месяц пришлём напоминание с кнопкой оплаты.\n\n"
            "Сейчас можете сразу перейти на сайт и поддержать проект — кнопка ниже. "  # noqa: E501
            "Оплата проходит на Donation Alerts.\n\n"
            "Отключить напоминания: /da_remind_off",
            reply_markup=kb,
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "donate:tr")
async def donate_tribute(cb: CallbackQuery) -> None:
    s = get_settings()
    web, tg = s.tribute_url_web.strip(), s.tribute_url_tg.strip()
    if isinstance(cb.message, Message):
        if not web and not tg:
            await cb.message.edit_text(
                "Ссылки Tribute не заданы. Администратору: укажите TRIBUTE_URL_WEB и/или "  # noqa: E501
                "TRIBUTE_URL_TG в настройках (.env).",
                reply_markup=donate_back_kb(),
            )
        else:
            await cb.message.edit_text(
                TEXT_TR, reply_markup=tribute_links_kb(web, tg)
            )  # noqa: E501
    await cb.answer()


@router.callback_query(_auth, F.data == "donate:st")
async def donate_stars_start(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(DonateStates.waiting_star_amount)
    await state.update_data({_STAR_AMOUNT_KEY: None})
    text = (
        "Звёзды Telegram: введите количество звёзд для списания\n\n"
        "Затем вы сможете выбрать разовый платёж или ежемесячное напоминание "
        "повторить ту же сумму.\n\n"
        "/cancel — отменить ввод."
    )
    if isinstance(cb.message, Message):
        await cb.message.edit_text(text, reply_markup=donate_back_kb())
    await cb.answer()


@router.message(
    _auth,
    StateFilter(DonateStates.waiting_star_amount),
    Command("cancel"),
)
async def donate_stars_cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Ввод отменён.", reply_markup=main_menu_kb())


@router.message(_auth, StateFilter(DonateStates.waiting_star_amount), F.text)
async def donate_stars_amount(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if raw == MAIN_MENU_BUTTON_BACK_TO_MAIN:
        await state.clear()
        await message.answer("Главное меню.", reply_markup=main_menu_kb())
        return
    if not raw.isdigit():
        await message.answer(
            f"Нужно целое число от {MIN_TELEGRAM_STARS_DONATION} "
            f"до {MAX_TELEGRAM_STARS_DONATION}."
        )
        return
    n = int(raw)
    if n < MIN_TELEGRAM_STARS_DONATION or n > MAX_TELEGRAM_STARS_DONATION:
        await message.answer(
            f"Допустимо от {MIN_TELEGRAM_STARS_DONATION} до {MAX_TELEGRAM_STARS_DONATION}."  # noqa: E501
        )
        return
    await state.update_data({_STAR_AMOUNT_KEY: n})
    await message.answer(
        "Как оформляем оплату звёздами?",
        reply_markup=star_freq_kb(),
    )


@router.callback_query(
    _auth,
    StateFilter(DonateStates.waiting_star_amount),
    F.data.in_({"donate:sf:o", "donate:sf:m"}),
)
async def donate_stars_freq(cb: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    stars = data.get(_STAR_AMOUNT_KEY)
    if not isinstance(stars, int):
        await cb.answer(
            "Сначала введите число звёзд сообщением.", show_alert=True
        )  # noqa: E501
        return
    monthly = cb.data.endswith(":m")
    await state.clear()
    try:
        await _send_star_invoice(cb.bot, cb.from_user.id, stars, monthly)
    except Exception as e:
        logger.exception("send_invoice failed: %s", e)
        await cb.answer(
            "Не удалось выставить счёт. Попробуйте позже.", show_alert=True
        )  # noqa: E501
        return
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await cb.answer()


@router.callback_query(_auth, F.data.startswith("donate:pm:"))
async def donate_repeat_monthly_invoice(
    cb: CallbackQuery, state: FSMContext
) -> None:  # noqa: E501
    await state.clear()
    try:
        stars = int(cb.data.split(":")[2])
    except (IndexError, ValueError):
        await cb.answer("Некорректные данные", show_alert=True)
        return
    if (
        stars < MIN_TELEGRAM_STARS_DONATION or stars > MAX_TELEGRAM_STARS_DONATION
    ):  # noqa: E501
        await cb.answer("Недопустимая сумма", show_alert=True)
        return
    try:
        await _send_star_invoice(cb.bot, cb.from_user.id, stars, monthly=True)
    except Exception as e:
        logger.exception("send_invoice failed: %s", e)
        await cb.answer("Не удалось выставить счёт.", show_alert=True)
        return
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await cb.answer("Откройте счёт выше и оплатите звёздами.")


@router.callback_query(_auth, F.data == "donate:rem:off")
async def donate_reminder_off(
    cb: CallbackQuery, db_user: User, session
) -> None:  # noqa: E501
    ok = await StarDonationService(session).deactivate_for_user(db_user.id)
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=None)
        if ok:
            await cb.message.answer("Напоминания отключены.")
        else:
            await cb.message.answer(
                "Активной подписки с напоминаниями не было."
            )  # noqa: E501
    await cb.answer()


@router.callback_query(_auth, F.data == "donate:da_rem:off")
async def donate_da_reminder_off(
    cb: CallbackQuery, db_user: User, session
) -> None:  # noqa: E501
    ok = await DonationAlertsReminderService(session).deactivate_for_user(
        db_user.id
    )  # noqa: E501
    if isinstance(cb.message, Message):
        await cb.message.edit_reply_markup(reply_markup=None)
        if ok:
            await cb.message.answer("Напоминания о Donation Alerts отключены.")
        else:
            await cb.message.answer("Активного напоминания не было.")
    await cb.answer()
