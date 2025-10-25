"""
Settings handlers including language selection
"""
from datetime import datetime

import aiogram
import pytz
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.i18n import gettext as _
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import User
from bot.handlers.private import admin_router
from bot.keyboards.inline import get_language_keyboard, get_timezone_keyboard, get_timezone_search_keyboard, \
    get_settings_keyboard
from bot.utils.helpers import get_language_name, format_timezone

settings_router = Router()


@settings_router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Show settings menu"""
    await message.delete()
    user = await User.get(message.from_user.id)
    await send_settings_menu(message, user)


# ---------------------- Language -------------------- #

@admin_router.callback_query(F.data == "settings_language")
async def settings_language(callback: CallbackQuery):
    """Show language selection"""
    user_id = int(callback.from_user.id)
    user: User = await User.get(user_id)
    logger.debug(user)

    text = _(
        "🌍 <b>Select Language</b>\n\n"
        "Current: {language}"
    ).format(language=get_language_name(user.language_code))

    await callback.message.edit_text(
        text,
        reply_markup=get_language_keyboard(current=user.language_code),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("lang_"))
async def language_selected(callback: CallbackQuery, session: AsyncSession):
    """Handle language selection"""
    language_code = callback.data.split("_")[1]

    # Validate language
    if language_code not in ['en', 'uz', 'ru']:
        await callback.answer(_("❌ Invalid language"), show_alert=True)
        return

    # Update user language
    user = await User.get(callback.from_user.id)
    await User.update(
        id_=user.id,
        language_code=language_code
    )

    new_language_text = get_language_name(language_code)

    await callback.message.edit_text(
        _("✅ Language changed to {new_language}!\n\n"
          "You can change it anytime in /settings").format(new_language=new_language_text),
        parse_mode="HTML"
    )

    await callback.answer()


@admin_router.message(Command("language"))
async def cmd_language(message: Message):
    """Direct language command"""
    user = await User.get(message.from_user.id)

    text = _(
        "🌍 <b>Select Language\n\n"
        "Current: {language}"
    ).format(language=get_language_name(user.language_code))

    await message.answer(
        text,
        reply_markup=get_language_keyboard(current=user.language_code),
        parse_mode="HTML"
    )


async def send_settings_menu(target, user: User):
    """
    Reusable function to send or edit the settings menu.

    Args:
        target: Can be a Message or CallbackQuery
        user: User instance
    """
    text = _(
        "⚙️ <b>Settings</b>\n\n"
        "Current configuration:\n"
        "🌍 Language: {language}\n"
        "💱 Currency: {currency}\n"
        "🕐 Timezone: {timezone}\n\n"
        "What would you like to change?"
    ).format(
        language=get_language_name(user.language_code),
        currency=user.currency,
        timezone=format_timezone(user.timezone)
    )

    reply_markup = get_settings_keyboard()

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        await target.answer()

    elif isinstance(target, Message):
        await target.answer(
            text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


# ==================== TIMEZONE SETTINGS ====================

@admin_router.callback_query(F.data == "settings_timezone")
async def settings_timezone(callback: CallbackQuery, session: AsyncSession):
    """Show timezone selection"""
    user = await User.get(callback.from_user.id)

    try:
        tz = pytz.timezone(user.timezone)
        current_time = datetime.now(tz).strftime("%H:%M %Z")
        utc_offset = datetime.now(tz).strftime("%z")
    except:
        current_time = datetime.now().strftime("%H:%M")
        utc_offset = "+0000"

    text = _(
        "🕐 <b>Select Timezone</b>\n\n"
        "Current: {timezone}\n"
        "Local time: {time}\n"
        "UTC offset: {offset}\n\n"
        "Choose a timezone region:"
    ).format(
        timezone=format_timezone(user.timezone),
        time=current_time,
        offset=utc_offset
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_timezone_keyboard(current=user.timezone),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("tz_region_"))
async def timezone_region_selected(callback: CallbackQuery, session: AsyncSession):
    """Show timezones for selected region"""
    region = callback.data.split("tz_region_")[1]

    user = await User.get(callback.from_user.id)

    text = _(
        "🕐 <b>Select Timezone - {region}</b>\n\n"
        "Current: {timezone}\n\n"
        "Choose your city:"
    ).format(
        region=region.replace("_", " ").title(),
        timezone=format_timezone(user.timezone)
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_timezone_search_keyboard(region, current=user.timezone),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("set_timezone:"))
async def timezone_selected(callback: CallbackQuery, session: AsyncSession):
    """Handle timezone selection"""
    timezone_str = callback.data.split("set_timezone:")[1]  # ✅ fixed parsing

    # Validate timezone
    try:
        pytz.timezone(timezone_str)
    except pytz.UnknownTimeZoneError:
        await callback.answer("❌ Invalid timezone", show_alert=True)
        return

    # Update user timezone
    user = await User.get(callback.from_user.id)
    await User.update(id_=user.id, timezone=timezone_str)

    # Get current time in new timezone
    tz = pytz.timezone(timezone_str)
    current_time = datetime.now(tz).strftime("%H:%M")
    utc_offset = datetime.now(tz).strftime("%z")
    utc_offset = f"{utc_offset[:3]}:{utc_offset[3:]}" if utc_offset else "+00:00"

    success_message = _(
        "✅ Timezone changed to {timezone}!\n\n"
        "🕐 Local time: {time}\n"
        "📍 UTC offset: {offset}\n\n"
        "All timestamps will now use this timezone."
    ).format(
        timezone=format_timezone(timezone_str),
        time=current_time,
        offset=utc_offset
    )

    await callback.message.edit_text(success_message, parse_mode="HTML")
    await callback.answer(f"✅ {format_timezone(timezone_str)}")


@admin_router.message(Command("timezone"))
async def cmd_timezone(message: Message, session: AsyncSession):
    """Direct timezone command"""
    user = await User.get(message.from_user.id)

    try:
        tz = pytz.timezone(user.timezone)
        current_time = datetime.now(tz).strftime("%H:%M")
    except:
        current_time = datetime.now().strftime("%H:%M")

    text = _(
        "🕐 <b>Select Timezone</b>\n\n"
        "Current: {timezone}\n"
        "Local time: {time}"
    ).format(
        timezone=format_timezone(user.timezone),
        time=current_time
    )

    await message.answer(
        text,
        reply_markup=get_timezone_keyboard(current=user.timezone),
        parse_mode="HTML"
    )


@settings_router.callback_query(F.data == "settings_main")
async def settings_main(callback: CallbackQuery):
    """Routes back to main settings menu"""
    user = await User.get(callback.from_user.id)
    await send_settings_menu(callback, user)
    await callback.answer()


# ==================== PLACEHOLDER HANDLERS ====================

@admin_router.callback_query(F.data == "settings_categories")
async def settings_categories(callback: CallbackQuery):
    """Manage categories (placeholder)"""
    await callback.answer("🏷️ Category management coming soon!", show_alert=True)


@admin_router.callback_query(F.data == "settings_currency")
async def settings_currency(callback: CallbackQuery):
    """Manage currencies (placeholder)"""
    await callback.answer("💲 Currency management coming soon!", show_alert=True)


@admin_router.callback_query(F.data == "settings_budgets")
async def settings_budgets(callback: CallbackQuery):
    """Manage budgets (placeholder)"""
    await callback.answer("🎯 Budget management coming soon!", show_alert=True)


@admin_router.callback_query(F.data == "settings_notifications")
async def settings_notifications(callback: CallbackQuery):
    """Manage notifications (placeholder)"""
    await callback.answer("🔔 Notification settings coming soon!", show_alert=True)


@admin_router.callback_query(F.data == "settings_export")
async def settings_export(callback: CallbackQuery):
    """Export data (placeholder)"""
    await callback.answer("📥 Data export coming soon!", show_alert=True)


@admin_router.callback_query(F.data == "settings_delete")
async def settings_delete(callback: CallbackQuery):
    """Delete account (placeholder)"""
    await callback.answer("🗑️ Account deletion coming soon!", show_alert=True)


@admin_router.callback_query(F.data == "settings_close")
async def settings_close(callback: CallbackQuery):
    """Close settings"""
    await callback.message.delete()
    await callback.answer()