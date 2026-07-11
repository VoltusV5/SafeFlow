import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton

from vpn_bot.config import get_settings
from vpn_bot.db.models import User
from vpn_bot.enums import VpnProtocol
from vpn_bot.exceptions import TooManyKeysError
from vpn_bot.filters import AdminFilter
from vpn_bot.keyboards import admin_menu_kb, dm_flow_kb, reset_keys_all_confirm_kb
from vpn_bot.texts import KEYS_INVALIDATED_SINGLE, KEYS_RESET_BROADCAST
from vpn_bot.services.admin_digest_service import send_admin_digest
from vpn_bot.services.admin_user_export_service import (
    build_admin_users_traffic_handshake_report,
)
from vpn_bot.services.amnezia_protocols import (
    provision_wireguard_admin_key,
    provision_xray_admin_key,
)
from vpn_bot.services.key_service import KeyService
from vpn_bot.services.notification_service import NotificationService
from vpn_bot.services.user_service import UserService
from vpn_bot.utils.moscow_schedule import yesterday_moscow_date

router = Router(name="admin")
_admin = AdminFilter()

logger = logging.getLogger(__name__)


class AdminStates(StatesGroup):
    waiting_notify = State()
    waiting_dm_target = State()
    waiting_dm_draft = State()
    waiting_adm_newkey_proto = State()


async def _resolve_target(session, arg: str) -> User | None:
    raw = arg.strip()
    us = UserService(session)
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return await us.get_by_tg_id(int(raw))
    return await us.find_by_username(raw.lstrip("@"))


@router.message(_admin, Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer(
        "Админ-панель.\n"
        "Кнопки ниже и команды:\n"
        "/ban @user|id — запретить доступ\n"
        "/unban @user|id — вернуть доступ\n"
        "/delkeys @user|id — сбросить конфигурации пользователя и уведомить его\n"
        "/msg — сообщение одному пользователю (черновик + /sendmsg, как рассылка)\n"
        "/passunlock <id|@user> — сбросить счётчик неверных паролей\n\n"
        "Кнопка «Сброс конфигураций всем» — отключить все ключи и уведомить всех.\n"
        "Рассылка: черновик → /sendnotification, отмена — /cansel или /cancel.\n\n"
        "/admin_report — полный дайджест за вчера (МСК), как в 08:00 утра, "
        "+ 3 графика CPU/RAM/сеть.\n"
        "/admin_users_export — txt: username, трафик за всё время, WG-handshake по каждому ключу "
        "(только чтение; wg dump сейчас).\n"
        "/admin_heavy_users — txt: пользователи, превысившие 100 ГБ за текущий месяц.\n"
        "/admin_newkey <имя> — сгенерировать ключ с заданным именем.\n"
        "/admin_delkey <имя> — удалить и деактивировать ключи по имени.\n"
        "/raw_config wg|xray — новый ключ на ваш аккаунт в БД + сырой клиентский файл.",
        reply_markup=admin_menu_kb(),
    )


@router.message(_admin, Command("raw_config"))
async def cmd_raw_config(message: Message, command: CommandObject, session) -> None:
    us = UserService(session)
    db_user = await us.get_by_tg_id(message.from_user.id)
    if db_user is None:
        await message.answer("Ваш аккаунт не найден в базе бота.")
        return
    arg = (command.args or "").strip().lower()
    if arg not in ("wg", "xray"):
        await message.answer(
            "Формат: /raw_config wg или /raw_config xray\n\n"
            "Создаётся запись ключа на ваш аккаунт (как «Новый ключ»), плюс файл с клиентской "
            "частью:\n"
            "• wg — client.wg.conf;\n"
            "• xray — client_xray.json.\n\n"
            "В key_value в БД хранится vpn:// (как обычно). Файл не пересылайте."
        )
        return
    await message.answer("Генерирую ключ и клиентский конфиг…")
    s = get_settings()
    ks = KeyService(session)
    try:
        if arg == "wg":
            raw_text, cfg = await asyncio.to_thread(provision_wireguard_admin_key, s)
            await ks.generate_one_from_provided(db_user, VpnProtocol.WIREGUARD, cfg)
            filename = "client.wg.conf"
        else:
            raw_text, cfg = await asyncio.to_thread(provision_xray_admin_key, s)
            await ks.generate_one_from_provided(db_user, VpnProtocol.XRAY, cfg)
            filename = "client_xray.json"
    except TooManyKeysError as e:
        await message.answer(str(e))
        return
    except Exception as e:
        logger.exception("raw_config")
        await message.answer(f"Не удалось сгенерировать: {e}"[:500])
        return
    data = raw_text.encode("utf-8")
    await message.answer_document(
        BufferedInputFile(data, filename=filename),
        caption="Ключ записан на ваш аккаунт в БД; в файле — клиентский конфиг. Не пересылайте.",
    )


@router.message(_admin, Command("admin_report"))
async def cmd_admin_report(message: Message) -> None:
    report_day = yesterday_moscow_date()
    await message.answer("Собираю дайджест за вчера по МСК…")
    await send_admin_digest(message.bot, report_day, purged_wg_keys=None)


@router.message(_admin, Command("admin_users_export"))
async def cmd_admin_users_export(message: Message, session, session_analytics) -> None:
    await message.answer(
        "Собираю txt: пользователи, трафик за всё время, handshake по ключам "
        "(чтение БД + wg show dump, ключи не трогаю)…"
    )
    try:
        body = await build_admin_users_traffic_handshake_report(session, session_analytics)
    except Exception:
        logger.exception("admin_users_export failed")
        await message.answer("Ошибка при сборе отчёта, см. лог бота.")
        return
    data = body.encode("utf-8")
    fn = "users_traffic_handshakes.txt"
    await message.answer_document(
        BufferedInputFile(data, filename=fn),
        caption="Пользователи: username, ГБ за всё время, handshake по ключам.",
    )


@router.message(_admin, Command("admin_heavy_users"))
async def cmd_admin_heavy_users(message: Message, session, session_analytics) -> None:
    from vpn_bot.services.traffic_stats_service import get_heavy_users_this_month
    await message.answer("Собираю пользователей, превысивших 100 ГБ за этот месяц...")
    try:
        users = await get_heavy_users_this_month(session, session_analytics, 100.0)
    except Exception:
        logger.exception("admin_heavy_users failed")
        await message.answer("Ошибка при сборе отчёта.")
        return
    
    if not users:
        await message.answer("Нет пользователей, превысивших 100 ГБ в этом месяце.")
        return
    
    lines = ["Пользователи > 100 ГБ за текущий месяц (МСК):"]
    for u, gb in users:
        un = f"@{u.tg_username}" if u.tg_username else f"ID:{u.tg_id}"
        lines.append(f"{un} — {gb:.2f} ГБ")
    
    data = "\n".join(lines).encode("utf-8")
    await message.answer_document(
        BufferedInputFile(data, filename="heavy_users.txt"),
        caption=f"Найдено пользователей: {len(users)}",
    )


@router.callback_query(_admin, F.data == "adm:resetkeys")
async def adm_resetkeys_prompt(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Отключить все активные конфигурации у всех пользователей в базе?\n"
            "Каждому авторизованному пользователю уйдёт уведомление о сбросе.",
            reply_markup=reset_keys_all_confirm_kb(),
        )
    await cb.answer()


@router.callback_query(_admin, F.data == "adm:resetkeys_no")
async def adm_resetkeys_no(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text("Сброс отменён.")
    await cb.answer()


@router.callback_query(_admin, F.data == "adm:resetkeys_yes")
async def adm_resetkeys_yes(cb: CallbackQuery, session) -> None:
    ks = KeyService(session)
    await ks.deactivate_all_active_keys()
    us = UserService(session)
    users = await us.list_authorized_users()
    for u in users:
        try:
            await cb.bot.send_message(u.tg_id, KEYS_RESET_BROADCAST)
        except TelegramBadRequest:
            pass
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            f"Готово: все активные конфигурации отключены. "
            f"Уведомления отправлены {len(users)} пользователям."
        )
    await cb.answer()


@router.callback_query(_admin, F.data == "adm:close")
async def adm_close(cb: CallbackQuery) -> None:
    if isinstance(cb.message, Message):
        await cb.message.edit_text("Панель закрыта.")
    await cb.answer()


_NOTIFY_IDS_KEY = "notify_message_ids"
_DM_IDS_KEY = "dm_message_ids"
_DM_TARGET_TG_KEY = "dm_target_tg_id"


@router.callback_query(_admin, F.data == "adm:notify")
async def adm_notify_start(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_notify)
    await state.update_data({_NOTIFY_IDS_KEY: []})
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            "Отправьте в чат всё, что нужно разослать — сколько угодно сообщений подряд "
            "(текст, фото, документы, стикеры и т.д.).\n\n"
            "Когда закончите, отправьте команду /sendnotification — бот скопирует "
            "все эти сообщения каждому авторизованному пользователю в том же порядке.\n\n"
            "/cansel или /cancel — отменить без отправки."
        )
    await cb.answer()


@router.message(_admin, StateFilter(AdminStates.waiting_notify), Command("sendnotification"))
async def adm_notify_commit(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    ids: list[int] = list(data.get(_NOTIFY_IDS_KEY, []))
    if not ids:
        await message.answer(
            "Черновик пустой. Сначала пришлите хотя бы одно сообщение, "
            "затем снова /sendnotification."
        )
        return

    await state.clear()
    us = UserService(session)
    users = await us.list_authorized_users()
    from_chat = message.chat.id
    bot = message.bot
    ok = 0
    failed = 0
    for u in users:
        for mid in ids:
            try:
                await bot.copy_message(
                    chat_id=u.tg_id,
                    from_chat_id=from_chat,
                    message_id=mid,
                )
                ok += 1
            except TelegramBadRequest:
                failed += 1

    NotificationService(session).log_broadcast(
        body=f"[рассылка: {len(ids)} сообщ., получателей: {len(users)}]",
        ok=failed == 0,
    )
    await message.answer(
        f"Готово. В черновике было сообщений: {len(ids)}, пользователей: {len(users)}. "
        f"Успешных копирований: {ok}, ошибок: {failed}."
    )


@router.message(
    _admin,
    StateFilter(AdminStates.waiting_notify),
    Command("cansel", "cancel"),
)
async def adm_notify_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Рассылка отменена.")


@router.message(_admin, StateFilter(AdminStates.waiting_notify))
async def adm_notify_accumulate(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer(
            "Сообщения-команды (начинающиеся с /) в черновик не добавляются. "
            "Сначала завершите или отмените рассылку (/sendnotification или /cansel), "
            "затем выполните команду."
        )
        return
    data = await state.get_data()
    ids: list[int] = list(data.get(_NOTIFY_IDS_KEY, []))
    ids.append(message.message_id)
    await state.update_data({_NOTIFY_IDS_KEY: ids})


async def _dm_execute_send(
    bot,
    admin_chat_id: int,
    target_tg_id: int,
    message_ids: list[int],
) -> tuple[bool, str]:
    try:
        await bot.send_message(target_tg_id, "Сообщение от администратора:")
    except TelegramBadRequest as e:
        return False, str(e)
    for mid in message_ids:
        try:
            await bot.copy_message(
                chat_id=target_tg_id,
                from_chat_id=admin_chat_id,
                message_id=mid,
            )
        except TelegramBadRequest:
            pass
    return True, ""


@router.message(_admin, Command("msg"))
async def cmd_msg(message: Message, command: CommandObject, state: FSMContext, session) -> None:
    raw = (command.args or "").strip()
    parts = raw.split(maxsplit=1)
    if len(parts) >= 2:
        await message.answer(
            "Ответ одному пользователю делается так:\n"
            "• /msg — затем id или @username, затем любое число сообщений и /sendmsg;\n"
            "• или /msg <id|@username> — сразу режим черновика.\n\n"
            "Текст в одной строке с /msg больше не используется."
        )
        return

    cur = await state.get_state()
    if cur in (
        AdminStates.waiting_dm_draft,
        AdminStates.waiting_dm_target,
    ):
        await message.answer(
            "Уже открыт режим сообщения пользователю. "
            "Завершите /sendmsg или отмените /cansel_dm."
        )
        return

    await state.clear()

    if not raw:
        await state.set_state(AdminStates.waiting_dm_target)
        await state.update_data({_DM_IDS_KEY: [], _DM_TARGET_TG_KEY: None})
        await message.answer(
            "Сообщение одному пользователю.\n"
            "Следующим сообщением отправьте Telegram ID (число) или @username.\n\n"
            "/cansel_dm — отмена."
        )
        return

    u = await _resolve_target(session, parts[0])
    if not u:
        await message.answer("Пользователь не найден в базе бота.")
        return

    await state.set_state(AdminStates.waiting_dm_draft)
    await state.update_data({_DM_TARGET_TG_KEY: u.tg_id, _DM_IDS_KEY: []})
    await message.answer(
        f"Получатель: tg_id={u.tg_id} (@{u.tg_username or '—'}).\n\n"
        "Отправьте в чат одно или несколько сообщений (текст, фото, файлы).\n"
        "Затем /sendmsg или кнопка «Подтвердить отправку».\n\n"
        "/cansel_dm или /cancel — отмена.",
        reply_markup=dm_flow_kb(),
    )


@router.message(
    _admin,
    StateFilter(AdminStates.waiting_dm_target),
    Command("cansel_dm", "cancel"),
)
async def dm_target_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(_admin, StateFilter(AdminStates.waiting_dm_target), F.text)
async def dm_target_receive(message: Message, state: FSMContext, session) -> None:
    u = await _resolve_target(session, message.text.strip())
    if not u:
        await message.answer("Пользователь не найден. Попробуйте снова или /cansel_dm.")
        return
    await state.set_state(AdminStates.waiting_dm_draft)
    await state.update_data({_DM_TARGET_TG_KEY: u.tg_id, _DM_IDS_KEY: []})
    await message.answer(
        f"Получатель: tg_id={u.tg_id} (@{u.tg_username or '—'}).\n\n"
        "Отправьте в чат одно или несколько сообщений (текст, фото, файлы).\n"
        "Затем /sendmsg или кнопка «Подтвердить отправку».\n\n"
        "/cansel_dm или /cancel — отмена.",
        reply_markup=dm_flow_kb(),
    )


@router.message(
    _admin,
    StateFilter(AdminStates.waiting_dm_draft),
    Command("sendmsg"),
)
async def dm_draft_sendmsg(message: Message, state: FSMContext, session) -> None:
    data = await state.get_data()
    ids: list[int] = list(data.get(_DM_IDS_KEY, []))
    target = data.get(_DM_TARGET_TG_KEY)
    if not target:
        await state.clear()
        await message.answer("Ошибка: получатель не задан.")
        return
    if not ids:
        await message.answer(
            "Черновик пустой. Добавьте сообщения в чат, затем снова /sendmsg."
        )
        return

    await state.clear()
    ok, err = await _dm_execute_send(
        message.bot,
        message.chat.id,
        int(target),
        ids,
    )
    if not ok:
        await message.answer(f"Не удалось доставить пользователю: {err}")
        return
    await message.answer(
        f"Готово. Отправлено {len(ids)} сообщ. пользователю tg_id={target}."
    )


@router.message(
    _admin,
    StateFilter(AdminStates.waiting_dm_draft),
    Command("cansel_dm", "cancel"),
)
async def dm_draft_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отправка пользователю отменена.")


@router.callback_query(
    _admin,
    StateFilter(AdminStates.waiting_dm_draft),
    F.data == "dm:commit",
)
async def dm_cb_commit(cb: CallbackQuery, state: FSMContext, session) -> None:
    data = await state.get_data()
    ids: list[int] = list(data.get(_DM_IDS_KEY, []))
    target = data.get(_DM_TARGET_TG_KEY)
    if not target:
        await state.clear()
        await cb.answer("Ошибка состояния", show_alert=True)
        return
    if not ids:
        await cb.answer(
            "Черновик пустой. Сначала отправьте сообщения в чат.",
            show_alert=True,
        )
        return

    await state.clear()
    chat_id = cb.message.chat.id if isinstance(cb.message, Message) else cb.from_user.id
    ok, err = await _dm_execute_send(cb.bot, chat_id, int(target), ids)
    if not ok:
        if isinstance(cb.message, Message):
            await cb.message.edit_text(f"Не удалось доставить: {err}")
        await cb.answer()
        return
    if isinstance(cb.message, Message):
        await cb.message.edit_text(
            f"Готово. Отправлено {len(ids)} сообщ. пользователю tg_id={target}."
        )
    await cb.answer()


@router.callback_query(
    _admin,
    StateFilter(AdminStates.waiting_dm_draft),
    F.data == "dm:abort",
)
async def dm_cb_abort(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(cb.message, Message):
        await cb.message.edit_text("Отправка отменена.")
    await cb.answer()


@router.message(_admin, StateFilter(AdminStates.waiting_dm_draft))
async def dm_draft_accumulate(message: Message, state: FSMContext) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer(
            "Сообщения, начинающиеся с /, в черновик не попадают. "
            "Используйте /sendmsg или /cansel_dm."
        )
        return
    data = await state.get_data()
    ids: list[int] = list(data.get(_DM_IDS_KEY, []))
    ids.append(message.message_id)
    await state.update_data({_DM_IDS_KEY: ids})


@router.message(_admin, Command("passunlock"))
async def cmd_passunlock(message: Message, command: CommandObject, session) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer(
            "Сбросить счётчик неверных паролей (после 50 попыток ввод блокируется):\n"
            "/passunlock <telegram_id или @username>"
        )
        return
    u = await _resolve_target(session, arg)
    if not u:
        await message.answer("Пользователь не найден.")
        return
    await UserService(session).reset_password_failures(u.tg_id)
    await message.answer(
        f"Счётчик неверных паролей сброшен для tg_id={u.tg_id}. "
        "Пользователь снова может вводить пароль."
    )


@router.message(_admin, Command("ban"))
async def cmd_ban(message: Message, command: CommandObject, session) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Формат: /ban @username или /ban <telegram_id>")
        return
    u = await _resolve_target(session, arg)
    if not u:
        await message.answer("Пользователь не найден в базе бота.")
        return
    await UserService(session).set_banned(u.tg_id, True)
    await message.answer(f"Забанен: tg_id={u.tg_id}, @{u.tg_username or 'без username'}")


@router.message(_admin, Command("unban"))
async def cmd_unban(message: Message, command: CommandObject, session) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Формат: /unban @username или /unban <telegram_id>")
        return
    u = await _resolve_target(session, arg)
    if not u:
        await message.answer("Пользователь не найден.")
        return
    await UserService(session).set_banned(u.tg_id, False)
    await message.answer(f"Разбанен: tg_id={u.tg_id}")


@router.message(_admin, Command("delkeys"))
async def cmd_delkeys(message: Message, command: CommandObject, session) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Формат: /delkeys @username или /delkeys <telegram_id>")
        return
    u = await _resolve_target(session, arg)
    if not u:
        await message.answer("Пользователь не найден.")
        return
    ks = KeyService(session)
    await ks.deactivate_user_keys(u.id)
    try:
        await message.bot.send_message(u.tg_id, KEYS_INVALIDATED_SINGLE)
    except TelegramBadRequest:
        pass
    await message.answer(
        f"Конфигурации отключены для tg_id={u.tg_id}. Пользователь уведомлён (если чат доступен)."
    )


def _admin_protocols_kb() -> InlineKeyboardMarkup:
    from vpn_bot.enums import VpnProtocol
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    line = []
    for p in VpnProtocol:
        line.append(InlineKeyboardButton(text=VpnProtocol.label(p), callback_data=f"admgen:proto:{p.value}"))
        if len(line) == 2:
            rows.append(line)
            line = []
    if line:
        rows.append(line)
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="admgen:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(_admin, Command("adm_newkey", "admin_newkey"))
async def cmd_adm_newkey(message: Message, command: CommandObject, state: FSMContext) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Формат: /admin_newkey <имя ключа>")
        return
    await state.update_data(adm_newkey_name=arg)
    await message.answer(f"Генерация ключа для '{arg}'. Выберите протокол:", reply_markup=_admin_protocols_kb())
    await state.set_state(AdminStates.waiting_adm_newkey_proto)

@router.callback_query(_admin, StateFilter(AdminStates.waiting_adm_newkey_proto), F.data == "admgen:cancel")
async def adm_newkey_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(cb.message, Message):
        await cb.message.edit_text("Генерация ключа отменена.")
    await cb.answer()

@router.callback_query(_admin, StateFilter(AdminStates.waiting_adm_newkey_proto), F.data.startswith("admgen:proto:"))
async def adm_newkey_proto_cb(cb: CallbackQuery, state: FSMContext, session, db_user: User) -> None:
    raw = cb.data.split(":")[2]
    from vpn_bot.enums import VpnProtocol, KeyDelivery
    from vpn_bot.exceptions import PeerGenerationError, TooManyKeysError
    from vpn_bot.services.key_service import KeyService
    from vpn_bot.handlers.delivery import deliver_secure_key
    try:
        protocol = VpnProtocol(raw)
    except ValueError:
        await cb.answer("Неизвестный тип профиля", show_alert=True)
        return
    
    data = await state.get_data()
    custom_name = data.get("adm_newkey_name")
    if not custom_name:
        await cb.answer("Имя ключа потеряно", show_alert=True)
        await state.clear()
        return

    if isinstance(cb.message, Message):
        try:
            await cb.message.edit_text(f"⏳ Генерирую конфигурацию ({protocol.value}) для '{custom_name}'…")
        except TelegramBadRequest:
            pass
    await cb.answer()

    ks = KeyService(session)
    try:
        key = await ks.generate_one(db_user, protocol, custom_name=custom_name)
    except Exception as e:
        logger.exception("adm_newkey failed")
        if isinstance(cb.message, Message):
            await cb.message.edit_text(f"❌ Ошибка генерации: {e}")
        await state.clear()
        return

    await state.clear()
    try:
        import html
        from aiogram.enums import ParseMode
        
        doc = BufferedInputFile(key.key_value.strip().encode("utf-8"), filename=key.config_filename)
        await cb.bot.send_document(cb.from_user.id, doc, caption=f"Конфигурация для: {custom_name}")
        
        body = key.key_value.strip()
        text = f'<pre><code class="language-python">{html.escape(body)}</code></pre>'
        if len(text) <= 4096:
            await cb.bot.send_message(cb.from_user.id, text, parse_mode=ParseMode.HTML)
        else:
            from vpn_bot.handlers.delivery import _pre_html_messages
            for part in _pre_html_messages(body):
                await cb.bot.send_message(cb.from_user.id, part, parse_mode=ParseMode.HTML)
    except Exception:
        logger.exception("adm_newkey delivery failed")
        if isinstance(cb.message, Message):
            await cb.message.edit_text("❌ Не удалось отправить конфигурацию.")
    else:
        if isinstance(cb.message, Message):
            try:
                await cb.message.delete()
            except TelegramBadRequest:
                pass


@router.message(_admin, Command("adm_delkey", "admin_delkey"))
async def cmd_adm_delkey(message: Message, command: CommandObject, session) -> None:
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("Формат: /admin_delkey <имя ключа>")
        return
    
    from vpn_bot.db.models import VpnKey
    from sqlalchemy import select, update
    from vpn_bot.services.revocation_service import revoke_key_on_server

    r = await session.execute(select(VpnKey).where(VpnKey.custom_name == arg, VpnKey.is_active.is_(True)))
    keys = r.scalars().all()
    
    if not keys:
        await message.answer(f"Активные ключи с именем '{arg}' не найдены.")
        return
    
    count = len(keys)
    for k in keys:
        await revoke_key_on_server(k)
        
    await session.execute(
        update(VpnKey).where(VpnKey.custom_name == arg, VpnKey.is_active.is_(True)).values(is_active=False)
    )
    await session.commit()
    await message.answer(f"Успешно удалено ключей с именем '{arg}': {count}")

