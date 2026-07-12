from aiogram import F, Router
from aiogram.filters import Command, StateFilter, and_f
from aiogram.types import (CallbackQuery, FSInputFile, LinkPreviewOptions,
                           Message)

from vpn_bot.constants import MAIN_MENU_BUTTON_BROWSER_EXTENSION
from vpn_bot.filters import AuthedFilter
from vpn_bot.handlers.contact_admin import ContactStates
from vpn_bot.handlers.report_problem import ReportProblemStates
from vpn_bot.keyboards import browser_extension_kb, main_menu_kb
from vpn_bot.paths import resolved_guides_src_dir
from vpn_bot.services.browser_extension_service import (
    SMARTPROXY_GUIDE_PDF_NAME, format_smartproxy_browser_message)
from vpn_bot.utils.text import split_telegram_message

router = Router(name="browser_extension")
_auth = AuthedFilter()
_not_in_contact = and_f(
    ~StateFilter(ContactStates.composing),
    ~StateFilter(ReportProblemStates.waiting_other),
)


@router.message(_auth, _not_in_contact, F.text == MAIN_MENU_BUTTON_BROWSER_EXTENSION)  # noqa: E501
@router.message(_auth, _not_in_contact, Command("browser_extension"))
async def browser_extension_entry(message: Message) -> None:
    from vpn_bot.config import get_settings

    text = format_smartproxy_browser_message(get_settings())
    parts = split_telegram_message(text)
    for i, part in enumerate(parts):
        markup = browser_extension_kb() if i == len(parts) - 1 else None
        await message.answer(
            part,
            parse_mode="HTML",
            reply_markup=markup,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )


@router.callback_query(_auth, F.data == "browser:pdf")
async def browser_extension_pdf(cb: CallbackQuery) -> None:
    path = resolved_guides_src_dir() / SMARTPROXY_GUIDE_PDF_NAME
    if not path.is_file():
        await cb.answer(
            "PDF пока не загружен на сервер. Обратитесь к администратору.",
            show_alert=True,
        )
        return
    if isinstance(cb.message, Message):
        await cb.message.answer_document(
            FSInputFile(path),
            caption="Подробная инструкция SmartProxy (с картинками).",
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "browser:back")
async def browser_extension_back(cb: CallbackQuery) -> None:
    await cb.answer()
    if isinstance(cb.message, Message):
        await cb.message.answer(
            "Главное меню.",
            reply_markup=main_menu_kb(),
        )
