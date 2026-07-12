#!/usr/bin/env python3
"""Смена аватарки бота (online/offline) для systemd ExecStartPre / ExecStopPost.  # noqa: E501

Источники по умолчанию (папка assets/):
  online  — «bot_avatar_online.jpg»
  offline — «bot_avatar_offline.jpg»

Переопределение: BOT_AVATAR_ONLINE / BOT_AVATAR_OFFLINE в .env (любой путь к PNG или JPEG).  # noqa: E501
Telegram принимает загрузку как JPEG; PNG конвертируется через Pillow.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from io import BytesIO
from pathlib import Path

# корень проекта: .../vpn-telegram-bot
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("set_bot_avatar")

def _fallback_assets_jpeg(online: bool) -> Path:  # noqa: E302
    name = "bot_avatar_online.jpg" if online else "bot_avatar_offline.jpg"
    return _PROJECT_ROOT / "assets" / name


def _ensure_jpeg_placeholder(path: Path, *, online: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("Pillow не установлен — положите свои изображения в %s", path.parent)  # noqa: E501
        raise
    w, h = 640, 640
    if online:
        bg = (39, 174, 96)
        im = Image.new("RGB", (w, h), bg)
        dr = ImageDraw.Draw(im)
        dr.ellipse((140, 140, 500, 500), fill=(236, 240, 241))
    else:
        bg = (44, 62, 80)
        im = Image.new("RGB", (w, h), bg)
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle((140, 140, 500, 500), radius=40, fill=(127, 140, 141))  # noqa: E501
        dr.line((200, 200, 440, 440), fill=(192, 57, 43), width=32)
        dr.line((440, 200, 200, 440), fill=(192, 57, 43), width=32)
    im.save(path, "JPEG", quality=88)
    logger.info("создан заглушечный JPEG: %s", path)


def _resolve_source_path(online: bool) -> Path:
    from vpn_bot.config import get_settings

    s = get_settings()
    raw = (s.bot_avatar_online_path if online else s.bot_avatar_offline_path).strip()  # noqa: E501
    if not raw:
        raw = str(
            _PROJECT_ROOT / "assets" / ("bot_avatar_online.jpg" if online else "bot_avatar_offline.jpg")  # noqa: E501
        )
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    if p.is_file():
        return p.resolve()

    fb = _fallback_assets_jpeg(online)
    if fb.is_file():
        logger.warning("файл из настроек не найден (%s), беру %s", p, fb)
        return fb.resolve()
    _ensure_jpeg_placeholder(fb, online=online)
    return fb.resolve()


def _build_profile_photo_upload(path: Path):
    from aiogram.types import BufferedInputFile, FSInputFile

    suf = path.suffix.lower()
    if suf in (".jpg", ".jpeg"):
        return FSInputFile(path)

    from PIL import Image

    im = Image.open(path)
    if im.mode in ("RGBA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[3])
        im_rgb = bg
    else:
        im_rgb = im.convert("RGB")
    buf = BytesIO()
    im_rgb.save(buf, format="JPEG", quality=92, optimize=True)
    data = buf.getvalue()
    return BufferedInputFile(data, filename="bot_profile.jpg")


async def _set_avatar(online: bool) -> None:
    from aiogram import Bot
    from aiogram.types import InputProfilePhotoStatic

    from vpn_bot.config import get_settings

    s = get_settings()
    path = _resolve_source_path(online)
    photo = _build_profile_photo_upload(path)
    bot = Bot(s.bot_token)
    try:
        try:
            await bot.remove_my_profile_photo()
        except Exception:
            logger.debug("remove_my_profile_photo (игнор)", exc_info=True)
        try:
            await bot.set_my_profile_photo(InputProfilePhotoStatic(photo=photo))  # noqa: E501
            logger.info("аватарка установлена (%s): %s", "online" if online else "offline", path)  # noqa: E501
        except Exception as e:
            logger.warning("не удалось установить аватарку (возможно, лимит): %s", e)  # noqa: E501
    finally:
        await bot.session.close()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("online", "offline"):
        print("Использование: set_bot_avatar.py online|offline", file=sys.stderr)  # noqa: E501
        sys.exit(2)
    os.chdir(_PROJECT_ROOT)
    from vpn_bot.config import get_settings

    get_settings.cache_clear()
    online = sys.argv[1] == "online"
    try:
        asyncio.run(_set_avatar(online))
    except Exception:
        logger.exception("не удалось сменить аватарку")
        sys.exit(1)


if __name__ == "__main__":
    main()
