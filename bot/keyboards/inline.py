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

def get_category_keyboard(categories):
    """
    Build inline keyboard for category selection using InlineKeyboardBuilder.
    categories: list of category objects with .id and .name
    """
    builder = InlineKeyboardBuilder()

    for category in categories:
        builder.button(
            text=category.name,
            callback_data=f"cat_{category.id}"
        )

    builder.adjust(2)

    return builder.as_markup()
