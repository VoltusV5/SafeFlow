from aiogram import F, Router
from aiogram.filters import Command, StateFilter, and_f
from aiogram.types import LinkPreviewOptions, Message

from vpn_bot.constants import MAIN_MENU_BUTTON_TELEGRAM_PROXY
from vpn_bot.filters import AuthedFilter
from vpn_bot.handlers.contact_admin import ContactStates
from vpn_bot.handlers.report_problem import ReportProblemStates
from vpn_bot.services.telegram_proxy_service import format_telegram_proxy_message
from vpn_bot.utils.text import split_telegram_message

router = Router(name="telegram_proxy")
_auth = AuthedFilter()
_not_in_contact = and_f(
    ~StateFilter(ContactStates.composing),
    ~StateFilter(ReportProblemStates.waiting_other),
)


@router.message(
    _auth, _not_in_contact, F.text == MAIN_MENU_BUTTON_TELEGRAM_PROXY
)  # noqa: E501
@router.message(_auth, _not_in_contact, Command("telegram_proxy"))
async def telegram_proxy_info(message: Message) -> None:
    from vpn_bot.config import get_settings

    text = format_telegram_proxy_message(get_settings())
    for part in split_telegram_message(text):
        await message.answer(
            part,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
