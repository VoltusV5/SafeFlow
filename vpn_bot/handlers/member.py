import logging
from datetime import UTC, datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter, and_f
from aiogram.fsm.context import FSMContext
from aiogram.types import (BufferedInputFile, CallbackQuery, FSInputFile,
                           LinkPreviewOptions, Message)

from vpn_bot.constants import (MAIN_MENU_BUTTON_BACK_TO_MAIN,
                               MAIN_MENU_BUTTON_SUPPORT_DONATE)
from vpn_bot.db.analytics_models import WhitelistBypassFeedback
from vpn_bot.db.models import User
from vpn_bot.enums import KeyDelivery, VpnProtocol
from vpn_bot.exceptions import (ContainerIssueError, PeerGenerationError,
                                TooManyKeysError)
from vpn_bot.filters import AuthedFilter
from vpn_bot.handlers.contact_admin import ContactStates
from vpn_bot.handlers.delivery import deliver_secure_key
from vpn_bot.handlers.report_problem import ReportProblemStates
from vpn_bot.keyboards import (amnezia_other_protocols_kb,  # noqa: F401
                               amnezia_protocols_kb, delivery_kb,
                               instructions_after_text_kb,
                               instructions_platform_kb,
                               instructions_telegram_proxy_kb, key_apps_kb,
                               main_menu_kb, protocols_kb,
                               safeflow_provider_kb, support_submenu_kb,
                               whitelist_bypass_kb,
                               whitelist_instruction_view_kb,
                               whitelist_platforms_kb, whitelist_vkturn_kb,
                               xray_variants_kb)
from vpn_bot.paths import resolved_guides_src_dir
from vpn_bot.services.key_service import KeyService
from vpn_bot.services.traffic_stats_service import TrafficStatsService
from vpn_bot.services.vkturn_xray_service import build_vkturn_vless_bundle
from vpn_bot.texts_whitelist_bypass import (VKTURN_TEST_INTRO_HTML,
                                            VKTURN_VK_LINK,
                                            WHITELIST_BYPASS_INTRO_HTML,
                                            WHITELIST_INSTR_MENU_HTML,
                                            WHITELIST_PLATFORM_CHUNKS)
from vpn_bot.utils.text import split_telegram_message

logger = logging.getLogger(__name__)


def _parse_wl_platform_cb(data: str | None) -> tuple[str, int] | None:
    if not data or not data.startswith("wl:p:"):
        return None
    raw = data.removeprefix("wl:p:")
    if ":" in raw:
        head, tail = raw.rsplit(":", 1)
        if tail.isdigit():
            return head, int(tail)
    return raw, 0


router = Router(name="member")
_auth = AuthedFilter()
_not_in_contact = and_f(
    ~StateFilter(ContactStates.composing),
    ~StateFilter(ReportProblemStates.waiting_other),
)

_CHOOSE_PROFILE_TEXT = (
    "Выбор VPN провайдера"
)

_WAITING_GENERATION_TEXT = "⏳ Генерирую конфигурацию…"

HELP_COMMANDS_TEXT = (
    "<b>Команды</b>\n"
    "/keys — активные профили\n"
    "/generate — новый ключ\n"
    "/mystats — статистика трафика\n"
    "/telegram_proxy — прокси для Telegram\n"
    "/browser_extension — расширение в браузере (SmartProxy)\n"
    "/donate — поддержать проект\n"
    "/help — эта справка и инструкции по платформам"
)


def _active_stats_lines(counts: dict[str, int]) -> str:
    lines: list[str] = []
    for p in VpnProtocol:
        n = counts.get(p.value, 0)
        if n > 0:
            lines.append(f"• {VpnProtocol.label(p)}: {n}")
    if not lines:
        return "Активных конфигураций по протоколам нет."
    return "\n".join(lines)


@router.message(_auth, _not_in_contact, Command("keys"))
async def my_keys(message: Message, db_user: User, session) -> None:
    ks = KeyService(session)
    counts = await ks.count_active_by_protocol(db_user.id)
    text = (
        "Ваши активные ключи:\n\n"
        + _active_stats_lines(counts)
        + "\n\nЧтобы получить ключ — «Новый ключ»"
    )
    for part in split_telegram_message(text):
        await message.answer(part)


@router.message(_auth, _not_in_contact, F.text == "Новый ключ")
@router.message(_auth, _not_in_contact, Command("generate"))
async def generate_entry(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_CHOOSE_PROFILE_TEXT, reply_markup=key_apps_kb())


@router.callback_query(_auth, F.data.startswith("gen:proto:"))
async def gen_pick_protocol(cb: CallbackQuery, state: FSMContext) -> None:
    raw = cb.data.split(":")[2]
    try:
        VpnProtocol(raw)
    except ValueError:
        await cb.answer("Неизвестный тип профиля", show_alert=True)
        return
    await state.update_data(protocol=raw)
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Как удобнее получить файл настройки?",
            reply_markup=delivery_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:back_proto")
async def gen_back_proto(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(protocol=None)
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            _CHOOSE_PROFILE_TEXT,
            reply_markup=key_apps_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:apps_back")
async def gen_apps_back(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            _CHOOSE_PROFILE_TEXT,
            reply_markup=key_apps_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:whitelist_beta")
async def gen_whitelist_bypass(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            WHITELIST_BYPASS_INTRO_HTML,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=whitelist_bypass_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:provider:safeflow")
async def gen_provider_safeflow(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "SafeFlow VPN",
            reply_markup=safeflow_provider_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:whitelist_test")
async def gen_whitelist_test(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            VKTURN_TEST_INTRO_HTML,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=whitelist_vkturn_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "wl:vkgen")
async def whitelist_vkturn_generate(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text("⏳ Генерирую ключ для Happ/v2RayTun + vk-turn…")  # noqa: E501
        except TelegramBadRequest:
            pass
    await cb.answer()

    try:
        host, peer, cmd, local_vless = build_vkturn_vless_bundle(VKTURN_VK_LINK)  # noqa: E501
    except ContainerIssueError as e:
        if isinstance(cb.message, Message):
            await cb.message.edit_text(
                f"❌ Не удалось сгенерировать ключ: {str(e)[:900]}",
                reply_markup=whitelist_vkturn_kb(),
            )
        return
    except Exception:
        logger.exception("wl:vkgen failed chat_id=%s", cb.from_user.id)
        if isinstance(cb.message, Message):
            await cb.message.edit_text(
                "❌ Ошибка генерации ключа. Попробуйте позже.",
                reply_markup=whitelist_vkturn_kb(),
            )
        return

    if isinstance(cb.message, Message):
        termux_stop = 'pkill -f "./client"\npgrep -af client'  # noqa: F841
        termux_bootstrap = (
            "pkg update -y && pkg install -y curl && cd \"$HOME\" && "
            "curl -L -o client "
            "https://github.com/cacggghp/vk-turn-proxy/releases/latest/download/client-android-arm64 "  # noqa: E501
            f"&& chmod +x client && ./client {cmd}"
        )
        termux_fast = (
            "termux-wake-lock\n"
            "pkill -f \"./client\" 2>/dev/null\n\n"
            f"./client {cmd.replace('-n 1', '-n 2')}"
        )
        termux_stop_one = 'pkill -f "./client"'
        termux_check_one = "pgrep -af client"
        await cb.message.edit_text(
            "<b>Happ/v2RayTun через vk-turn</b>\n\n"
            "<b>Для Termux (первая установка):</b>\n"
            f"<code>{termux_bootstrap}</code>\n\n"
            "<b>Для Termux (повторный запуск):</b>\n"
            f"<pre>{termux_fast}</pre>\n"
            "<b>Остановить туннель (в один клик):</b>\n"
            f"<code>{termux_stop_one}</code>\n\n"
            "<b>Проверить процесс (в один клик):</b>\n"
            f"<code>{termux_check_one}</code>\n\n"
            "<b>Импортируйте в Happ/v2RayTun эту ссылку:</b>\n"
            f"<code>{local_vless}</code>\n\n"
            "Порядок: сначала запустить Termux, вставить необходимые команды, дождаться "  # noqa: E501
            "<code>Established DTLS connection!</code>, потом включить профиль в Happ/v2RayTun.\n\n"  # noqa: E501
            "Termux: <a href=\"https://play.google.com/store/apps/details?id=com.termux&amp;hl=ru\">"  # noqa: E501
            "https://play.google.com/store/apps/details?id=com.termux&amp;hl=ru</a>\n"  # noqa: E501
            "Happ: <a href=\"https://play.google.com/store/apps/details?id=com.happproxy&amp;hl=ru\">"  # noqa: E501
            "https://play.google.com/store/apps/details?id=com.happproxy&amp;hl=ru</a>",  # noqa: E501
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=whitelist_vkturn_kb(),
        )


@router.callback_query(_auth, F.data == "wl:instr")
async def whitelist_instructions_menu(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            WHITELIST_INSTR_MENU_HTML,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=whitelist_platforms_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "wl:menu")
async def whitelist_back_to_intro(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            WHITELIST_BYPASS_INTRO_HTML,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=whitelist_bypass_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data.startswith("wl:p:"))
async def whitelist_platform_view(cb: CallbackQuery) -> None:
    parsed = _parse_wl_platform_cb(cb.data)
    if not parsed:
        await cb.answer()
        return
    slug, page = parsed
    chunks = WHITELIST_PLATFORM_CHUNKS.get(slug)
    if not chunks:
        await cb.answer("Раздел не найден", show_alert=True)
        return
    flat: list[str] = []
    for c in chunks:
        flat.extend(split_telegram_message(c, limit=3900))
    if not flat:
        await cb.answer("Раздел пуст", show_alert=True)
        return
    page = max(0, min(page, len(flat) - 1))
    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(
                flat[page],
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=whitelist_instruction_view_kb(slug, page, len(flat)),  # noqa: E501
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await cb.answer()
                return
            raise
    await cb.answer()


@router.callback_query(_auth, F.data == "wl:noop")
async def whitelist_pagination_noop(cb: CallbackQuery) -> None:
    await cb.answer()


@router.callback_query(_auth, F.data.in_({"wl:ok", "wl:bad"}))
async def whitelist_bypass_feedback(cb: CallbackQuery, session_analytics) -> None:  # noqa: E501
    works = cb.data == "wl:ok"
    session_analytics.add(
        WhitelistBypassFeedback(created_at=datetime.now(UTC), works=works)
    )
    await cb.answer("Спасибо за отзыв!" if works else "Записано.")


@router.callback_query(_auth, F.data == "gen:app:amnezia")
async def gen_app_amnezia(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Для приложения AmneziaVPN.\n\n"
            "Рекомендуемые Amnezia WG / Xray.\n"
            "«Другие протоколы» — OpenVPN / WireGuard / IPsec.",
            reply_markup=amnezia_protocols_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:amz:other")
async def gen_amnezia_other(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Другие протоколы для AmneziaVPN.",
            reply_markup=amnezia_other_protocols_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:app:xray")
async def gen_app_xray(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Для других приложений (не AmneziaVPN).\n\n"
            "Рекомендуемые приложения:\n"
            'Android: <a href="https://github.com/2dust/v2rayNG/releases">v2rayNG</a> / '  # noqa: E501
            '<a href="https://github.com/MatsuriDayo/NekoBoxForAndroid/releases">NekoBox</a> / '  # noqa: E501
            '<a href="https://play.google.com/store/apps/details?id=com.v2raytun.android">v2RayTun</a> / '  # noqa: E501
            '<a href="https://play.google.com/store/apps/details?id=com.happproxy">Happ</a>\n'  # noqa: E501
            'iOS: <a href="https://apps.apple.com/us/app/streisand/id6450534064">Streisand</a> / '  # noqa: E501
            '<a href="https://apps.apple.com/us/app/shadowrocket/id932747118">Shadowrocket</a>\n'  # noqa: E501
            'Desktop: <a href="https://github.com/MatsuriDayo/nekoray/releases">NekoRay</a> / '  # noqa: E501
            '<a href="https://github.com/2dust/v2rayN/releases">v2rayN</a>\n\n'
            "Выберите формат Xray-конфигурации:",
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=xray_variants_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:xray_apps_info")
async def gen_xray_apps_info(cb: CallbackQuery) -> None:
    text = (
        "<b>Рекомендуемые приложения для Xray</b>\n\n"
        "<b>Android:</b>\n"
        "• GitHub: "
        '<a href="https://github.com/2dust/v2rayNG/releases">v2rayNG</a> / '
        '<a href="https://github.com/MatsuriDayo/NekoBoxForAndroid/releases">NekoBox</a>\n'  # noqa: E501
        "• Google Play: "
        '<a href="https://play.google.com/store/apps/details?id=com.v2raytun.android">v2RayTun</a> / '  # noqa: E501
        '<a href="https://play.google.com/store/apps/details?id=com.happproxy">Happ</a>\n\n'  # noqa: E501
        "<b>iOS:</b> "
        '<a href="https://apps.apple.com/us/app/streisand/id6450534064">Streisand</a> / '  # noqa: E501
        '<a href="https://apps.apple.com/us/app/foxray/id6448898396">FoXray</a> / '  # noqa: E501
        '<a href="https://apps.apple.com/us/app/shadowrocket/id932747118">Shadowrocket</a>\n\n'  # noqa: E501
        "<b>Desktop:</b> "
        '<a href="https://github.com/MatsuriDayo/nekoray/releases">NekoRay</a> / '  # noqa: E501
        '<a href="https://github.com/2dust/v2rayN/releases">v2rayN</a>'
    )
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            text,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=xray_variants_kb(),
        )
    await cb.answer()


@router.callback_query(_auth, F.data == "gen:cancel")
async def gen_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(cb.message, Message):
        await cb.message.edit_text("Создание конфигурации отменено.")
    await cb.answer()


@router.callback_query(_auth, F.data.startswith("gen:deliv:"))
async def gen_deliver(cb: CallbackQuery, state: FSMContext, db_user: User, session) -> None:  # noqa: C901, E501
    data = await state.get_data()
    proto_raw = data.get("protocol")
    if not proto_raw:
        await cb.answer("Сначала выберите тип профиля", show_alert=True)
        return
    try:
        protocol = VpnProtocol(proto_raw)
    except ValueError:
        await cb.answer("Ошибка типа профиля", show_alert=True)
        return

    kind = cb.data.split(":")[2]
    try:
        delivery = KeyDelivery(kind)
    except ValueError:
        await cb.answer("Неизвестный способ", show_alert=True)
        return

    chat_id = cb.from_user.id
    bot = cb.bot
    ks = KeyService(session)

    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(
                _WAITING_GENERATION_TEXT,
                reply_markup=None,
            )
        except TelegramBadRequest:
            pass
    await cb.answer()

    try:
        key = await ks.generate_one(db_user, protocol)
    except TooManyKeysError as e:
        await bot.send_message(chat_id, str(e))
        if isinstance(cb.message, Message):
            try:
                await cb.message.edit_text(f"❌ {str(e)[:500]}")
            except TelegramBadRequest:
                pass
        return
    except PeerGenerationError as e:
        await bot.send_message(chat_id, e.message[:3500])
        if isinstance(cb.message, Message):
            try:
                await cb.message.edit_text(
                    "ℹ️ Не удалось выдать конфигурацию. Подробности — в сообщении ниже."  # noqa: E501
                )
            except TelegramBadRequest:
                pass
        return
    except Exception:
        logger.exception(
            "gen_deliver failed chat_id=%s protocol=%s delivery=%s",
            chat_id,
            protocol,
            delivery,
        )
        await bot.send_message(
            chat_id,
            "Не удалось сгенерировать ключ. Попробуйте позже или напишите в поддержку.",  # noqa: E501
        )
        if isinstance(cb.message, Message):
            try:
                await cb.message.edit_text(
                    "❌ Не удалось сгенерировать ключ. См. сообщение ниже."
                )
            except TelegramBadRequest:
                pass
        return

    await state.clear()
    try:
        await deliver_secure_key(bot, chat_id, key, delivery)
    except Exception:
        logger.exception(
            "deliver_secure_key failed chat_id=%s protocol=%s",
            chat_id,
            protocol,
        )
        if isinstance(cb.message, Message):
            try:
                await cb.message.edit_text(
                    "❌ Не удалось отправить конфигурацию. Напишите в поддержку."  # noqa: E501
                )
            except TelegramBadRequest:
                pass
        return

    if isinstance(cb.message, Message):
        try:
            await cb.message.delete()
        except TelegramBadRequest:
            await cb.message.edit_reply_markup(reply_markup=None)


@router.message(_auth, _not_in_contact, Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        HELP_COMMANDS_TEXT,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    await message.answer(
        "Выберите вашу платформу — пришлю краткую инструкцию.",
        reply_markup=instructions_platform_kb(),
    )


@router.message(_auth, _not_in_contact, F.text == "Инструкции")
async def instructions_entry(message: Message) -> None:
    await message.answer(
        "Выберите вашу платформу — пришлю краткую инструкцию.",
        reply_markup=instructions_platform_kb(),
    )


@router.message(_auth, _not_in_contact, F.text == MAIN_MENU_BUTTON_SUPPORT_DONATE)  # noqa: E501
async def support_submenu_open(message: Message) -> None:
    await message.answer(
        "Техподдержка и донат. Выберите действие.",
        reply_markup=support_submenu_kb(),
    )


@router.message(_auth, F.text == MAIN_MENU_BUTTON_BACK_TO_MAIN)
async def back_to_main_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Главное меню.",
        reply_markup=main_menu_kb(),
    )


INSTRUCTIONS = {
    "ios": (
        "iOS:\n"
        "1) Установите приложение Amnezia из appstore.\n"
        'Если приложение не отображается в AppStore при поиске, то нужно сменить регион на США в настройках "контента и покупок" устройства\n'  # noqa: E501
        "2) Получите ключ для подключения с помощью этого бота.\n"
        "3) Включите защищённое соединение в приложении."
    ),
    "android": (
        "Android:\n"
        "1) Установите приложение Amnezia: https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru \n"  # noqa: E501
        "или через github (APK файл): https://github.com/amnezia-vpn/amnezia-client/releases/tag/4.8.14.5 \n"  # noqa: E501
        "2) Получите ключ, файл или QR в этом боте.\n"
        "3) Импортируйте профиль и включите защищённое соединение."
    ),
    "win": (
        "Windows:\n"
        "1) Скачайте приложение Amnezia с github: https://github.com/amnezia-vpn/amnezia-client/releases/tag/4.8.14.5 \n файл AmneziaVPN_4.8.14.5_x64.exe \n"  # noqa: E501
        "2) Скопируйте ключ или файл настройки из этого бота и вставьте его в приложение.\n"  # noqa: E501
        "3) Активируйте защищённое соединение в программе."
    ),
    "mac": (
        "macOS:\n"
        "1) Установите приложение Amnezia через github: https://github.com/amnezia-vpn/amnezia-client/releases/tag/4.8.14.5 \n"  # noqa: E501
        "файл AmneziaVPN_4.8.14.5_macos.pkg \n"
        "2) Скопируйте ключ или файл конфигурации из этого бота.\n"
        "3) Включите защищённое соединение через меню приложения."
    ),
}

_GUIDE_PDF_NAMES = {"ios": "ios.pdf", "android": "android.pdf", "win": "windows.pdf"}  # noqa: E501


@router.message(_auth, _not_in_contact, Command("mystats"))
async def cmd_mystats(message: Message, db_user: User, session_analytics) -> None:  # noqa: E501
    lines, chart_buf = await TrafficStatsService(session_analytics).user_weekly_report(  # noqa: E501
        db_user.id
    )
    text = "\n".join(lines)
    for part in split_telegram_message(text):
        await message.answer(part)
    if chart_buf:
        await message.answer_photo(
            BufferedInputFile(chart_buf, filename="traffic_7d.png"),
            caption="Трафик за 7 дней (оценка по снимкам wg, ГБ/сутки).",
        )


@router.callback_query(_auth, F.data.startswith("help:pdf:"))
async def instructions_send_pdf(cb: CallbackQuery) -> None:
    parts = cb.data.split(":")
    if len(parts) < 3:
        await cb.answer("Неверный запрос.", show_alert=True)
        return
    plat = parts[2]
    pdf_name = _GUIDE_PDF_NAMES.get(plat)
    if not pdf_name or not isinstance(cb.message, Message):
        await cb.answer("Гайд для этой платформы не настроен.", show_alert=True)  # noqa: E501
        return
    path = resolved_guides_src_dir() / pdf_name
    if not path.is_file():
        await cb.answer(
            "PDF пока не загружен на сервер. Обратитесь к администратору.",
            show_alert=True,
        )
        return
    await cb.message.answer_document(
        FSInputFile(path),
        caption="Подробная инструкция (PDF).",
    )
    await cb.answer()


@router.callback_query(_auth, F.data.startswith("help:"))
async def instructions_pick(cb: CallbackQuery) -> None:
    key = cb.data.split(":")[1]
    if key == "close":
        if isinstance(cb.message, Message):
            await cb.message.edit_text("Закрыто.")
        await cb.answer()
        return
    if key == "back_platforms":
        if isinstance(cb.message, Message):
            await cb.message.edit_text(
                "Выберите вашу платформу — пришлю краткую инструкцию.",
                reply_markup=instructions_platform_kb(),
            )
        await cb.answer()
        return
    if key == "alwayson":
        if isinstance(cb.message, Message):
            await cb.message.edit_text(
                "1) установить VPN\n"
                "2) Откройте настройки VPN в настройках системы.\n"
                "3) Включите опцию постоянного подключения (Always-on / Всегда включен).\n"  # noqa: E501
                "4) В настройках приложения выберите \"маршрутизация\" или \"туннелирование\", выберите: приложения:\n"  # noqa: E501
                "-  которые будут идти только через VPN, или те, которые будут идти без VPN,\n"  # noqa: E501
                "- или выберите, чтобы весь трафик шёл через VPN.\n"
                "5) Сохраните настройки",
                reply_markup=instructions_platform_kb(),
            )
        await cb.answer()
        return
    if key == "telegram_proxy":
        if isinstance(cb.message, Message):
            await cb.message.edit_text(
                "<b>Telegram proxy</b>\n\n"
                "Зачем: если полный VPN недоступен или неудобен, можно направить "  # noqa: E501
                "<b>только трафик Telegram</b> через прокси на нашем сервере (MTProto или SOCKS — "  # noqa: E501
                "ссылки выдаёт бот в разделе «Telegram proxy»). Так Telegram иногда снова открывается "  # noqa: E501
                "там, где обычный интернет его режет или не пускает.\n\n"
                "<b>Важно:</b> у части сетей и операторов такой прокси ведёт себя нестабильно или "  # noqa: E501
                "не подключается — для отдельных пользователей это нормально. Тогда надёжнее "  # noqa: E501
                "полноценный VPN (ключ в этом боте).\n\n"
                "Готовые ссылки и параметры — в главном меню: кнопка «Telegram proxy».",  # noqa: E501
                parse_mode="HTML",
                link_preview_options=LinkPreviewOptions(is_disabled=True),
                reply_markup=instructions_telegram_proxy_kb(),
            )
        await cb.answer()
        return
    text = INSTRUCTIONS.get(key, "Раздел в разработке.")
    markup = (
        instructions_after_text_kb(key)
        if key in _GUIDE_PDF_NAMES
        else None
    )
    if isinstance(cb.message, Message):
        await cb.message.edit_text(text, reply_markup=markup)
    await cb.answer()
