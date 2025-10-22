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


def get_category_keyboard(categories) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if not categories:
        print("⚠️ No categories passed to keyboard builder!")
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Other", callback_data="cat_9")]
        ])

    builder.row(
        *[
            InlineKeyboardButton(text=cat.name, callback_data=f"cat_{cat.id}")
            for cat in categories
        ],
        width=2
    )
    return builder.as_markup()
