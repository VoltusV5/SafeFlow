from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.types import User as TgUser

from vpn_bot.config import get_settings
from vpn_bot.constants import (MAIN_MENU_BUTTON_BACK_TO_MAIN,
                               REPORT_PROBLEM_PRESETS)
from vpn_bot.db.models import ProblemReport, User
from vpn_bot.filters import AuthedFilter
from vpn_bot.keyboards import main_menu_kb, report_problem_kb

router = Router(name="report_problem")
_auth = AuthedFilter()


class ReportProblemStates(StatesGroup):
    waiting_other = State()


async def _notify_admins_report(
    message: Message,
    *,
    category_label: str,
    user_comment: str | None,
    db_user: User,
    session,
    sender: TgUser | None = None,
) -> bool:
    """sender: при вызове из callback укажите cb.from_user — у cb.message автор сообщения бот."""  # noqa: E501
    settings = get_settings()
    admins = settings.admin_ids
    if not admins:
        return False
    who = sender or message.from_user
    uid = who.id if who else 0
    un = (who.username or "").strip() if who else ""
    lines = [
        "Сообщение о проблеме с сервисом",
        "",
        "Связь с клиентом:",
    ]
    if un:
        lines.append(f"@{un}")
        lines.append(f"https://t.me/{un}")
    else:
        lines.append("username не указан — писать только ответом в чат бота")
    lines.append(f"Telegram ID: {uid}")
    lines.append("")
    lines.append(f"Тип: {category_label}")
    if user_comment:
        lines.append("")
        lines.append("Описание:")
        lines.append(user_comment)
    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4090] + "…"
    for aid in admins:
        try:
            await message.bot.send_message(aid, text)
        except TelegramBadRequest:
            continue
    session.add(
        ProblemReport(
            user_id=db_user.id,
            category=category_label[:255],
            body=(user_comment[:8000] if user_comment else None),
        )
    )
    await session.flush()
    return True


@router.message(_auth, F.text == "Сообщить о проблеме")
async def report_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Что именно не работает? Выберите вариант — администратор получит уведомление.\n\n"  # noqa: E501
        "Пункт «Другое» — опишите ситуацию одним сообщением.\n\n"
        "/cancel_report — отмена.",
        reply_markup=report_problem_kb(),
    )


@router.message(_auth, StateFilter(ReportProblemStates.waiting_other), Command("cancel_report"))  # noqa: E501
async def report_cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_menu_kb())


@router.callback_query(_auth, F.data == "fb:cancel")
async def report_cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text("Отменено.")
        except TelegramBadRequest:
            await cb.message.answer("Отменено.")
    await cb.answer()


@router.callback_query(_auth, F.data.startswith("fb:c:"))
async def report_cb_preset(cb: CallbackQuery, state: FSMContext, session, db_user: User) -> None:  # noqa: E501
    await state.clear()
    if not isinstance(cb.message, Message):
        await cb.answer()
        return
    idx_s = (cb.data or "").split(":")[-1]
    try:
        idx = int(idx_s)
    except ValueError:
        await cb.answer("Неверный вариант.", show_alert=True)
        return
    if idx < 0 or idx >= len(REPORT_PROBLEM_PRESETS):
        await cb.answer("Неверный вариант.", show_alert=True)
        return
    label = REPORT_PROBLEM_PRESETS[idx]
    ok = await _notify_admins_report(
        cb.message,
        category_label=label,
        user_comment=None,
        db_user=db_user,
        session=session,
        sender=cb.from_user,
    )
    if not ok:
        await cb.answer(
            "Не удалось отправить: не заданы администраторы (ADMIN_IDS).",
            show_alert=True,
        )
        return
    try:
        await cb.message.edit_text(
            "Спасибо, мы получили ваше сообщение. Администратор увидит его в боте "  # noqa: E501
            "и при необходимости ответит вам здесь."
        )
    except TelegramBadRequest:
        await cb.message.answer(
            "Спасибо, мы получили ваше сообщение. Администратор увидит его в боте "  # noqa: E501
            "и при необходимости ответит вам здесь."
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "fb:other")
async def report_cb_other(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReportProblemStates.waiting_other)
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(
                "Опишите проблему одним сообщением (текстом).\n\n"
                "/cancel_report — отмена без отправки."
            )
        except TelegramBadRequest:
            await cb.message.answer(
                "Опишите проблему одним сообщением (текстом).\n\n"
                "/cancel_report — отмена без отправки."
            )
    await cb.answer()


@router.message(_auth, StateFilter(ReportProblemStates.waiting_other))
async def report_other_text(message: Message, state: FSMContext, session, db_user: User) -> None:  # noqa: E501
    if message.text and message.text.strip() == MAIN_MENU_BUTTON_BACK_TO_MAIN:
        await state.clear()
        await message.answer("Главное меню.", reply_markup=main_menu_kb())
        return
    if message.text and message.text.startswith("/"):
        await message.answer(
            "Сейчас ожидается описание проблемы текстом или команда /cancel_report."  # noqa: E501
        )
        return
    if not message.text or not message.text.strip():
        await message.answer("Нужен текстовый ответ. Опишите проблему или /cancel_report.")  # noqa: E501
        return
    body = message.text.strip()
    ok = await _notify_admins_report(
        message,
        category_label="Другое",
        user_comment=body,
        db_user=db_user,
        session=session,
    )
    await state.clear()
    if not ok:
        await message.answer(
            "Не удалось отправить: в настройках бота не заданы администраторы (ADMIN_IDS).",  # noqa: E501
            reply_markup=main_menu_kb(),
        )
        return
    await message.answer(
        "Спасибо, описание передано администратору. При необходимости он ответит вам здесь.",  # noqa: E501
        reply_markup=main_menu_kb(),
    )
