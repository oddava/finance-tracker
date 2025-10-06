from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def currency_choice_ikm() -> InlineKeyboardMarkup:
    ikb = InlineKeyboardBuilder()

    ikb.row(
        InlineKeyboardButton(text="USD($)", callback_data="currency_set_USD"),
        InlineKeyboardButton(text="RUB(₽)", callback_data="currency_set_RUB"),
        InlineKeyboardButton(text="UZS(сўм)", callback_data="currency_set_UZS"),
    )

    return ikb.as_markup()