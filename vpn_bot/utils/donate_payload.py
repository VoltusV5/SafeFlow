from __future__ import annotations

from vpn_bot.constants import MAX_TELEGRAM_STARS_DONATION, MIN_TELEGRAM_STARS_DONATION


def build_star_invoice_payload(monthly: bool, stars: int) -> str:
    return f"s|{'m' if monthly else 'o'}|{stars}"


def parse_star_invoice_payload(raw: str) -> tuple[bool, int] | None:
    parts = raw.split("|")
    if len(parts) != 3 or parts[0] != "s" or parts[1] not in ("o", "m"):
        return None
    try:
        stars = int(parts[2])
    except ValueError:
        return None
    if (
        stars < MIN_TELEGRAM_STARS_DONATION or stars > MAX_TELEGRAM_STARS_DONATION
    ):  # noqa: E501
        return None
    return (parts[1] == "m", stars)


def reminder_text(stars: int) -> str:
    return (
        f"Прошёл месяц — если хотите, можете снова поддержать проект звёздами ({stars} ⭐) (СБП, МИР). "  # noqa: E501
        "Кнопка ниже выставит такой же счёт.\n\n"
        "Следующее напоминание придёт не раньше чем через месяц. "
        "Отключить рассылку: кнопка «Отключить напоминания» или /stars_remind_off."  # noqa: E501
    )


def da_reminder_text() -> str:  # noqa: E302
    return (
        "Прошёл месяц — если хотите, можете снова поддержать проект через Donation Alerts (СБП, МИР) "  # noqa: E501
        "(ссылка на оплату ниже).\n\n"
        "Следующее такое напоминание придёт не раньше чем через месяц. "
        "Чтобы больше не получать эти сообщения: кнопка «Отключить напоминания» "  # noqa: E501
        "или команда /da_remind_off."
    )
