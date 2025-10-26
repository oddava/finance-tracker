import pytz
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.i18n import gettext as _
from loguru import logger

from bot.utils.helpers import format_timezone


def currency_choice_ikm() -> InlineKeyboardMarkup:
    ikb = InlineKeyboardBuilder()

    ikb.row(
        InlineKeyboardButton(text="[$]USD", callback_data="currency_set_USD"),
        InlineKeyboardButton(text="[₽]RUB", callback_data="currency_set_RUB"),
        InlineKeyboardButton(text="[сўм]UZS", callback_data="currency_set_UZS"),
    )

    return ikb.as_markup()


def get_category_keyboard(categories) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not categories:
        logger.warning("⚠️ No categories passed to keyboard builder!")
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Other", callback_data="cat_9")],
            [InlineKeyboardButton(text="Cancel", callback_data="cancel")],
        ])

    builder.row(
        *[
            InlineKeyboardButton(text=cat.name, callback_data=f"cat_{cat.id}")
            for cat in categories
        ],
        width=2
    )
    return builder.as_markup()


def get_currency_keyboard(current: str = None) -> InlineKeyboardMarkup:
    """Create currency selection keyboard with more options"""
    currencies = [
        ("🇺🇿 UZS - So'm", "curr_UZS"),
        ("🇺🇸 USD - Dollar", "curr_USD"),
        ("🇪🇺 EUR - Euro", "curr_EUR"),
        ("🇷🇺 RUB - Ruble", "curr_RUB"),
        ("🇬🇧 GBP - Pound", "curr_GBP"),
        ("🇯🇵 JPY - Yen", "curr_JPY"),
        ("🇨🇳 CNY - Yuan", "curr_CNY"),
        ("🇰🇿 KZT - Tenge", "curr_KZT"),
        ("🇹🇷 TRY - Lira", "curr_TRY"),
    ]

    buttons = []
    for name, callback in currencies:
        # Add checkmark for current currency
        if current and callback.endswith(current):
            name = f"✅ {name}"
        buttons.append([InlineKeyboardButton(text=name, callback_data=callback)])

    # Add back button
    buttons.append([InlineKeyboardButton(text="« Back", callback_data="settings_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_language_keyboard(current: str = None) -> InlineKeyboardMarkup:
    """Create language selection keyboard"""
    languages = [
        ("🇬🇧 English", "lang_en"),
        ("🇺🇿 O'zbekcha", "lang_uz"),
        ("🇷🇺 Русский", "lang_ru")
    ]

    buttons = []
    for name, callback in languages:
        # Add checkmark for current language
        if current and callback.endswith(current):
            name = f"✅ {name}"
        buttons.append([InlineKeyboardButton(text=name, callback_data=callback)])

    # Add back button
    buttons.append([InlineKeyboardButton(text="« Back", callback_data="settings_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Create settings menu keyboard"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=_("🌍 Language"), callback_data="settings_language"),
            InlineKeyboardButton(text=_("💱 Currency"), callback_data="settings_currency")
        ],
        [
            InlineKeyboardButton(text=_("🏷️ Categories"), callback_data="settings_categories"),
            InlineKeyboardButton(text=_("🎯 Budgets"), callback_data="settings_budgets")
        ],
        [
            InlineKeyboardButton(text=_("🔔 Notifications"), callback_data="settings_notifications"),
            InlineKeyboardButton(text=_("🕐 Timezone"), callback_data="settings_timezone")
        ],
        [
            InlineKeyboardButton(text=_("📥 Export Data"), callback_data="settings_export"),
            InlineKeyboardButton(text=_("🗑️ Delete Account"), callback_data="settings_delete")
        ],
        [
            InlineKeyboardButton(text=_("❌ Close"), callback_data="settings_close")
        ]
    ])
    return keyboard


def get_timezone_keyboard(current: str = None) -> InlineKeyboardMarkup:
    """
    Create timezone region selection keyboard

    Shows major regions first, then user can drill down
    """
    regions = [
        ("🌏 Asia", "tz_region_Asia"),
        ("🌍 Europe", "tz_region_Europe"),
        ("🌎 America", "tz_region_America"),
        ("🌏 Pacific", "tz_region_Pacific"),
        ("🌍 Africa", "tz_region_Africa"),
        ("❄️ Antarctica", "tz_region_Antarctica"),
    ]

    buttons = [[InlineKeyboardButton(text=name, callback_data=callback)] for name, callback in regions]

    # Add back button
    buttons.append([InlineKeyboardButton(text="« Back", callback_data="settings_main")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_timezone_search_keyboard(region: str, current: str = None) -> InlineKeyboardMarkup:
    """
    Create timezone selection keyboard for a specific region.
    """
    all_timezones = pytz.all_timezones
    region_timezones = [tz for tz in all_timezones if tz.startswith(region + "/")]

    priority_cities = {
        "Asia": [
            "Asia/Tashkent", "Asia/Dubai", "Asia/Shanghai", "Asia/Tokyo",
            "Asia/Seoul", "Asia/Singapore", "Asia/Bangkok", "Asia/Kolkata",
            "Asia/Karachi", "Asia/Tehran", "Asia/Jerusalem", "Asia/Hong_Kong"
        ],
        "Europe": [
            "Europe/London", "Europe/Paris", "Europe/Berlin", "Europe/Moscow",
            "Europe/Rome", "Europe/Madrid", "Europe/Amsterdam", "Europe/Istanbul",
            "Europe/Athens", "Europe/Vienna", "Europe/Prague", "Europe/Warsaw"
        ],
        "America": [
            "America/New_York", "America/Chicago", "America/Los_Angeles",
            "America/Mexico_City", "America/Toronto", "America/Sao_Paulo",
            "America/Buenos_Aires", "America/Lima", "America/Bogota"
        ],
        "Pacific": [
            "Pacific/Auckland", "Pacific/Sydney", "Pacific/Fiji",
            "Pacific/Honolulu", "Pacific/Guam"
        ],
        "Africa": [
            "Africa/Cairo", "Africa/Johannesburg", "Africa/Lagos",
            "Africa/Nairobi", "Africa/Casablanca"
        ],
        "Antarctica": [
            "Antarctica/McMurdo", "Antarctica/DumontDUrville"
        ]
    }

    priority = [tz for tz in priority_cities.get(region, []) if tz in region_timezones]
    timezones_to_show = priority[:10] if priority else region_timezones[:10]

    buttons = []
    for tz in timezones_to_show:
        label = format_timezone(tz)
        if tz == current:
            label = f"✅ {label}"
        buttons.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"set_timezone:{tz}"
            )
        ])

    # Optional: Add a back button
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="settings_timezone")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)