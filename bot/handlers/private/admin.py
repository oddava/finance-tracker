
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from bot.core.config import settings
from bot.database import BotSetting
from filters.admin_filter import AdminFilter

admin_router = Router()


@admin_router.message(Command("maintenance"), AdminFilter())
async def toggle_maintenance(message: Message):
    """Toggle maintenance mode (admin only)"""

    # Check if user is admin
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("❌ You don't have permission to use this command.")
        return

    # Toggle maintenance mode
    maintenance_status = await BotSetting.filter_first(BotSetting.key=="maintenance_mode")

    is_enabled = str(maintenance_status.value).lower() == "true"
    settings.MAINTENANCE_MODE = not is_enabled
    maintenance_status.value = "False" if is_enabled else "True"
    await maintenance_status.save()

    maintenance_status = str(maintenance_status.value).lower() == "true"
    status = "🔧 ENABLED" if maintenance_status else "✅ DISABLED"


    await message.answer(
        f"<b>Maintenance Mode: {status}</b>\n\n"
        f"Current state: {'Under maintenance' if maintenance_status else 'Normal operation'}",
        parse_mode="HTML"
    )
    logger.warning(
        f"🔧 Maintenance mode {status} by admin {message.from_user.id} "
        f"(@{message.from_user.username})"
    )

@admin_router.message(Command("status"), AdminFilter())
async def check_status(message: Message):
    """Check bot status (admin only)"""
    maintenance_status = await BotSetting.filter_first(BotSetting.key=="maintenance_mode")

    status = "🔧 Under Maintenance" if str(maintenance_status.value).lower() == "true" else "✅ Running"

    await message.answer(
        f"<b>Bot Status</b>\n\n"
        f"Mode: {status}\n"
        f"Webhook: {'Enabled' if settings.USE_WEBHOOK else 'Polling'}",
        parse_mode="HTML"
    )