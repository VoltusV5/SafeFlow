import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from vpn_bot.config import get_settings
from vpn_bot.filters import AuthedFilter
from vpn_bot.keyboards import contact_flow_kb, main_menu_kb, report_problem_kb

router = Router(name="contact")
_auth = AuthedFilter()
logger = logging.getLogger(__name__)

CONTACT_IDS_KEY = "contact_msg_ids"


class ContactStates(StatesGroup):
    composing = State()


CONTACT_INTRO = (
    "Напишите администратору: отправьте в чат одно или несколько сообщений "
    "(текст, фото, документы — как нужно).\n\n"
    "Сообщения пока только у вас. Когда всё готово, нажмите «Подтвердить отправку» "  # noqa: E501
    "ниже — тогда они уйдут администраторам.\n\n"
    "/cancel_contact — отменить без отправки."
)


@router.message(_auth, F.text == "Написать администратору")
async def contact_entry(message: Message, state: FSMContext) -> None:
    await state.set_state(ContactStates.composing)
    await state.update_data({CONTACT_IDS_KEY: []})
    await message.answer(
        CONTACT_INTRO,
        reply_markup=contact_flow_kb(),
    )


@router.message(
    _auth, StateFilter(ContactStates.composing), Command("cancel_contact")
)  # noqa: E501
async def contact_cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Обращение отменено.", reply_markup=main_menu_kb())


@router.message(
    _auth, StateFilter(ContactStates.composing), F.text == "Сообщить о проблеме"
)  # noqa: E501
async def contact_switch_to_report(
    message: Message, state: FSMContext
) -> None:  # noqa: E501
    await state.clear()
    await message.answer(
        "Что именно не работает? Выберите вариант — администратор получит уведомление.\n\n"  # noqa: E501
        "Пункт «Другое» — опишите ситуацию одним сообщением.\n\n"
        "/cancel_report — отмена.",
        reply_markup=report_problem_kb(),
    )


@router.message(_auth, StateFilter(ContactStates.composing))
async def contact_accumulate(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer(
            "Это похоже на команду. Добавьте обычные сообщения для администратора "  # noqa: E501
            "или отмените обращение: /cancel_contact"
        )
        return
    data = await state.get_data()
    ids: list[int] = list(data.get(CONTACT_IDS_KEY, []))
    ids.append(message.message_id)
    await state.update_data({CONTACT_IDS_KEY: ids})


@router.callback_query(
    _auth, StateFilter(ContactStates.composing), F.data == "ct:abort"
)  # noqa: E501
async def contact_cb_abort(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(cb.message, Message):
        await cb.message.edit_text("Отправка отменена.")
    await cb.answer()
    await cb.bot.send_message(
        cb.from_user.id,
        "Меню:",
        reply_markup=main_menu_kb(),
    )


@router.callback_query(
    _auth, StateFilter(ContactStates.composing), F.data == "ct:commit"
)  # noqa: E501
async def contact_cb_commit(
    cb: CallbackQuery, state: FSMContext
) -> None:  # noqa: C901, E501
    data = await state.get_data()
    ids: list[int] = list(data.get(CONTACT_IDS_KEY, []))
    if not ids:
        await cb.answer(
            "Пока нет сообщений. Напишите что-нибудь в чат, затем снова нажмите кнопку.",  # noqa: E501
            show_alert=True,
        )
        return

    await state.clear()
    settings = get_settings()
    admins = settings.admin_ids
    if not admins:
        if isinstance(cb.message, Message):
            await cb.message.edit_text(
                "Не удалось отправить: в настройках бота не заданы администраторы (ADMIN_IDS)."  # noqa: E501
            )
        await cb.answer()
        return

    uid = cb.from_user.id
    chat_user = (
        cb.message.chat.id if isinstance(cb.message, Message) else cb.from_user.id
    )  # noqa: E501
    un = cb.from_user.username
    user_line = f"@{un}" if un else "(без username)"
    header = (
        "Обращение от пользователя\n" f"Telegram ID: {uid}\n" f"Username: {user_line}\n"
    )

    payload_ok = False
    header_ok = False
    for aid in admins:
        try:
            await cb.bot.send_message(aid, header)
            header_ok = True
        except TelegramBadRequest as e:
            logger.warning("contact admin header to aid=%s: %s", aid, e)
            continue
        for mid in ids:
            try:
                await cb.bot.copy_message(
                    chat_id=aid,
                    from_chat_id=chat_user,
                    message_id=mid,
                )
                payload_ok = True
            except TelegramBadRequest as e1:
                try:
                    await cb.bot.forward_message(
                        chat_id=aid,
                        from_chat_id=chat_user,
                        message_id=mid,
                    )
                    payload_ok = True
                except TelegramBadRequest as e2:
                    logger.warning(
                        "contact admin copy+forward aid=%s mid=%s: %s | %s",
                        aid,
                        mid,
                        e1,
                        e2,
                    )

    if isinstance(cb.message, Message):
        if payload_ok:
            await cb.message.edit_text(
                f"Готово. В очереди было {len(ids)} ваших сообщений — они отправлены "  # noqa: E501
                f"администраторам."
            )
        elif header_ok:
            await cb.message.edit_text(
                "Администраторам ушли только ваш Telegram ID и username, "
                "но сами сообщения переслать не удалось (ограничение Telegram по типу контента). "  # noqa: E501
                "Попробуйте отправить текстом или напишите в поддержку из меню ещё раз."  # noqa: E501
            )
        else:
            await cb.message.edit_text(
                "Не удалось связаться с администраторами. "
                "Проверьте ADMIN_IDS в настройках бота и что админы не блокировали бота."  # noqa: E501
            )
    await cb.answer()
    if payload_ok:
        tail = "Готово. Если нужно, администратор ответит вам здесь в чате."
    elif header_ok:
        tail = "Проверьте сообщение выше — возможно, нужно повторить отправку текстом."  # noqa: E501
    else:
        tail = "Проверьте настройки бота и попробуйте снова."
    await cb.bot.send_message(uid, tail, reply_markup=main_menu_kb())
