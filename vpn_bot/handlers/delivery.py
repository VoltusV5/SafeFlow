from __future__ import annotations

import html
import io

import qrcode
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import BufferedInputFile

from vpn_bot.db.models import VpnKey
from vpn_bot.enums import KeyDelivery, VpnProtocol

_HEADER_PREFIX = "Конфигурация ("

_MULTI_MESSAGE_COPY_HINT = (
    "Чтобы скопировать ключ целиком:\n"
    "• Выделите все сообщения с ключом подряд, которые пришли от бота.\n"
    "• Нажмите «Копировать».\n\n"
    "Длинная ссылка vpn:// не помещается в одно сообщение — нужно скопировать все части вместе."  # noqa: E501
)

_PROTOCOLS_TEXT_DELIVERY_COPY_HINT = frozenset(
    {
        VpnProtocol.IPSEC.value,
        VpnProtocol.OPENVPN.value,
        VpnProtocol.OPENVPN_CLOAK.value,
        VpnProtocol.OPENVPN_SS.value,
    }
)

def _header_and_body(key: VpnKey) -> tuple[str, str]:  # noqa: E302
    raw = key.key_value
    s = raw.lstrip()
    if s.startswith(_HEADER_PREFIX) and "\n" in s:
        i = s.index("\n")
        return s[:i].strip(), s[i + 1 :].lstrip()  # noqa: E203
    protocol = VpnProtocol(key.protocol)
    header = f"{_HEADER_PREFIX}{VpnProtocol.base_label(protocol)}):"
    return header, raw.strip()


def _pre_html_messages(body: str, max_len: int = 4096) -> list[str]:
    open_tag, close_tag = "<pre>", "</pre>"
    overhead = len(open_tag) + len(close_tag)
    out: list[str] = []
    rest = body
    while rest:
        low, high = 1, len(rest)
        best = 0
        while low <= high:
            mid = (low + high) // 2
            elen = len(html.escape(rest[:mid]))
            if overhead + elen <= max_len:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        if best == 0:
            best = 1
        take = rest[:best]
        rest = rest[best:]
        out.append(f"{open_tag}{html.escape(take)}{close_tag}")
    return out


async def deliver_secure_key(
    bot: Bot,
    chat_id: int,
    key: VpnKey,
    delivery: KeyDelivery,
) -> None:
    header, body = _header_and_body(key)

    if delivery == KeyDelivery.MESSAGE:
        await bot.send_message(chat_id, header)
        for part in _pre_html_messages(body):
            await bot.send_message(
                chat_id,
                part,
                parse_mode=ParseMode.HTML,
            )
        if key.protocol in _PROTOCOLS_TEXT_DELIVERY_COPY_HINT:
            await bot.send_message(chat_id, _MULTI_MESSAGE_COPY_HINT)
        return

    if delivery == KeyDelivery.FILE:
        doc = BufferedInputFile(
            body.encode("utf-8"),
            filename=key.config_filename,
        )
        await bot.send_document(chat_id, doc)
        return

    qr = qrcode.QRCode(version=None, box_size=4, border=2)
    qr.add_data(body)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    photo = BufferedInputFile(buf.read(), filename="qr.png")
    await bot.send_photo(chat_id, photo)
