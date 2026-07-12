from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)

from vpn_bot.constants import (MAIN_MENU_BUTTON_BACK_TO_MAIN,
                               MAIN_MENU_BUTTON_BROWSER_EXTENSION,
                               MAIN_MENU_BUTTON_SUPPORT_DONATE,
                               MAIN_MENU_BUTTON_TELEGRAM_PROXY,
                               REPORT_PROBLEM_PRESETS)


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Новый ключ")],
            [
                KeyboardButton(text=MAIN_MENU_BUTTON_BROWSER_EXTENSION),
                KeyboardButton(text=MAIN_MENU_BUTTON_TELEGRAM_PROXY),
            ],
            [
                KeyboardButton(text="Инструкции"),
                KeyboardButton(text=MAIN_MENU_BUTTON_SUPPORT_DONATE),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие в меню",
    )


def support_submenu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Написать администратору"),
                KeyboardButton(text="Сообщить о проблеме"),
            ],
            [KeyboardButton(text="Поддержать")],
            [KeyboardButton(text=MAIN_MENU_BUTTON_BACK_TO_MAIN)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Техподдержка и донат",
    )


def browser_extension_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подробная инструкция (PDF)",
                    callback_data="browser:pdf",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="browser:back")],
        ]
    )


def protocols_kb() -> InlineKeyboardMarkup:
    # Legacy: keep function for compatibility; now entry starts from app selector.  # noqa: E501
    return key_apps_kb()


def whitelist_bypass_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Работает при белых", callback_data="wl:ok"),  # noqa: E501
                InlineKeyboardButton(
                    text="❌ Не работает при белых",
                    callback_data="wl:bad",
                ),
            ],
            [
                InlineKeyboardButton(text="Инструкции", callback_data="wl:instr"),  # noqa: E501
                InlineKeyboardButton(text="Назад", callback_data="gen:apps_back"),  # noqa: E501
            ],
        ]
    )


def whitelist_vkturn_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сгенерировать ключ Happ/v2RayTun",
                    callback_data="wl:vkgen",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="gen:apps_back")],  # noqa: E501
        ]
    )


def whitelist_platforms_kb() -> InlineKeyboardMarkup:
    from vpn_bot.texts_whitelist_bypass import WHITELIST_PLATFORM_MENU

    rows: list[list[InlineKeyboardButton]] = []
    pair: list[InlineKeyboardButton] = []
    for slug, label in WHITELIST_PLATFORM_MENU:
        pair.append(
            InlineKeyboardButton(text=label, callback_data=f"wl:p:{slug}")
        )
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([InlineKeyboardButton(text="Назад", callback_data="wl:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def whitelist_instruction_view_kb(
    slug: str, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    """Одно сообщение: текст + навигация по страницам + возврат к списку систем."""  # noqa: E501
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav_btns: list[InlineKeyboardButton] = []
        if page > 0:
            nav_btns.append(
                InlineKeyboardButton(
                    text="◀",
                    callback_data=f"wl:p:{slug}:{page - 1}",
                )
            )
        nav_btns.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="wl:noop",
            )
        )
        if page < total_pages - 1:
            nav_btns.append(
                InlineKeyboardButton(
                    text="▶",
                    callback_data=f"wl:p:{slug}:{page + 1}",
                )
            )
        rows.append(nav_btns)
    rows.append(
        [InlineKeyboardButton(text="Назад", callback_data="wl:instr")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def key_apps_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="SafeFlow VPN",
                    callback_data="gen:provider:safeflow",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="hyper.space VPN (дополнительный VPN провайдер)",
                    callback_data="gen:whitelist_beta",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Тестовый обход белых списков",
                    callback_data="gen:whitelist_test",
                ),
            ],
        ]
    )


def safeflow_provider_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Для приложения AmneziaVPN",
                    callback_data="gen:app:amnezia",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Для других приложений",
                    callback_data="gen:app:xray",
                ),
            ],
            [InlineKeyboardButton(text="Назад", callback_data="gen:apps_back")],  # noqa: E501
        ]
    )


def amnezia_protocols_kb() -> InlineKeyboardMarkup:
    from vpn_bot.enums import VpnProtocol

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=VpnProtocol.label(VpnProtocol.AMNEZIA_WG),
                    callback_data=f"gen:proto:{VpnProtocol.AMNEZIA_WG.value}",
                ),
                InlineKeyboardButton(
                    text=VpnProtocol.label(VpnProtocol.XRAY),
                    callback_data=f"gen:proto:{VpnProtocol.XRAY.value}",
                ),
            ],
            [InlineKeyboardButton(text="Другие протоколы", callback_data="gen:amz:other")],  # noqa: E501
            [InlineKeyboardButton(text="Назад", callback_data="gen:apps_back")],  # noqa: E501
        ]
    )


def amnezia_other_protocols_kb() -> InlineKeyboardMarkup:
    from vpn_bot.enums import VpnProtocol

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=VpnProtocol.label(VpnProtocol.OPENVPN_CLOAK),
                    callback_data=f"gen:proto:{VpnProtocol.OPENVPN_CLOAK.value}",  # noqa: E501
                ),
                InlineKeyboardButton(
                    text=VpnProtocol.label(VpnProtocol.OPENVPN),
                    callback_data=f"gen:proto:{VpnProtocol.OPENVPN.value}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=VpnProtocol.label(VpnProtocol.OPENVPN_SS),
                    callback_data=f"gen:proto:{VpnProtocol.OPENVPN_SS.value}",
                ),
                InlineKeyboardButton(
                    text=VpnProtocol.label(VpnProtocol.WIREGUARD),
                    callback_data=f"gen:proto:{VpnProtocol.WIREGUARD.value}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=VpnProtocol.label(VpnProtocol.IPSEC),
                    callback_data=f"gen:proto:{VpnProtocol.IPSEC.value}",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="gen:app:amnezia")],  # noqa: E501
        ]
    )


def xray_variants_kb() -> InlineKeyboardMarkup:
    from vpn_bot.enums import VpnProtocol

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="VLESS (REALITY) ⭐",
                    callback_data=f"gen:proto:{VpnProtocol.XRAY_VLESS.value}",
                ),
                InlineKeyboardButton(
                    text="Trojan",
                    callback_data=f"gen:proto:{VpnProtocol.XRAY_TROJAN.value}",
                )
            ],

            [InlineKeyboardButton(text="Назад", callback_data="gen:apps_back")],  # noqa: E501
        ]
    )


def delivery_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Текстом", callback_data="gen:deliv:message"),
                InlineKeyboardButton(
                    text="Файлом", callback_data="gen:deliv:file"),
            ],
            [InlineKeyboardButton(
                text="QR-код", callback_data="gen:deliv:qr")],
            [
                InlineKeyboardButton(
                    text="Назад к выбору типа",
                    callback_data="gen:back_proto",
                )
            ],
        ]
    )


def instructions_platform_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="iOS", callback_data="help:ios"),
                InlineKeyboardButton(
                    text="Android", callback_data="help:android"),
            ],
            [
                InlineKeyboardButton(text="Windows", callback_data="help:win"),
                InlineKeyboardButton(text="macOS", callback_data="help:mac"),
            ],
            [
                InlineKeyboardButton(
                    text="Telegram proxy",
                    callback_data="help:telegram_proxy",
                )
            ],
            [InlineKeyboardButton(text="Как сделать постоянный VPN", callback_data="help:alwayson")],  # noqa: E501
            [InlineKeyboardButton(text="Закрыть", callback_data="help:close")],
        ]
    )


def instructions_telegram_proxy_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="К выбору платформы",
                    callback_data="help:back_platforms",
                )
            ],
        ]
    )


def instructions_after_text_kb(platform_key: str) -> InlineKeyboardMarkup:
    """Кнопки под краткой инструкцией (iOS / Android / Windows)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подробный гайд",
                    callback_data=f"help:pdf:{platform_key}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="К выбору платформы",
                    callback_data="help:back_platforms",
                )
            ],
        ]
    )


def admin_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Уведомление всем",
                                  callback_data="adm:notify")],
            [
                InlineKeyboardButton(
                    text="Сброс конфигураций всем",
                    callback_data="adm:resetkeys",
                )
            ],
            [InlineKeyboardButton(
                text="Закрыть админ-панель", callback_data="adm:close")],
        ]
    )


def dm_flow_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Подтвердить отправку", callback_data="dm:commit")],
            [InlineKeyboardButton(text="Отмена", callback_data="dm:abort")],
        ]
    )


def report_problem_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=label, callback_data=f"fb:c:{i}")]
        for i, label in enumerate(REPORT_PROBLEM_PRESETS)
    ]
    rows.append([InlineKeyboardButton(text="Другое", callback_data="fb:other")])  # noqa: E501
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="fb:cancel")])  # noqa: E501
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contact_flow_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Подтвердить отправку", callback_data="ct:commit")],
            [InlineKeyboardButton(text="Отмена", callback_data="ct:abort")],
        ]
    )


def donate_methods_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Donation Alerts (от 10 ₽, СБП, МИР)",
                    callback_data="donate:da",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Tribute (от 100 ₽, СБП, МИР)",
                    callback_data="donate:tr",
                )
            ],
            [InlineKeyboardButton(text="Звёзды Telegram (СБП, МИР)",
                                  callback_data="donate:st")],
        ]
    )


def donate_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="К способам оплаты",
                                  callback_data="donate:menu")],
        ]
    )


def tribute_links_kb(url_web: str, url_tg: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if url_web.strip():
        rows.append(
            [InlineKeyboardButton(text="Tribute — веб", url=url_web.strip())]
        )
    if url_tg.strip():
        rows.append(
            [InlineKeyboardButton(
                text="Tribute — в Telegram", url=url_tg.strip())]
        )
    rows.append(
        [InlineKeyboardButton(text="К способам оплаты",
                              callback_data="donate:menu")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def da_freq_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Разово", callback_data="donate:da:o"),  # noqa: E501
                InlineKeyboardButton(text="Ежемесячно", callback_data="donate:da:m"),  # noqa: E501
            ],
            [
                InlineKeyboardButton(
                    text="К способам оплаты",
                    callback_data="donate:menu",
                )
            ],
        ]
    )


def da_monthly_reminder_kb(url: str) -> InlineKeyboardMarkup:
    safe = (url or "https://www.donationalerts.com/").strip()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=safe)],
            [
                InlineKeyboardButton(
                    text="Отключить напоминания",
                    callback_data="donate:da_rem:off",
                )
            ],
        ]
    )


def star_freq_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Разово", callback_data="donate:sf:o"),
                InlineKeyboardButton(
                    text="Ежемесячно", callback_data="donate:sf:m"),
            ],
            [InlineKeyboardButton(text="К способам оплаты",
                                  callback_data="donate:menu")],
        ]
    )


def star_monthly_reminder_kb(stars: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Оплатить {stars} ⭐",
                    callback_data=f"donate:pm:{stars}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отключить напоминания",
                    callback_data="donate:rem:off",
                )
            ],
        ]
    )


def reset_keys_all_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, сбросить у всех",
                    callback_data="adm:resetkeys_yes",
                )
            ],
            [InlineKeyboardButton(
                text="Отмена", callback_data="adm:resetkeys_no")],
        ]
    )
