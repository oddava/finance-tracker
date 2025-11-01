import csv
import io
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.core.config import settings
from bot.database import BotSetting, Transaction, Budget, Category, User
from bot.database.engine import db
from bot.filters.admin_filter import AdminFilter
from bot.services.admin_service import BroadcastService
from bot.services.user_service import UserService
from bot.utils import measure, get_broadcast_sent_text, get_confirm_broadcast_text, get_broadcast_message, \
    get_total_users, get_new_users_today, get_active_users_today, get_active_users_week, \
    get_transactions_count_today, get_transactions_count_total, get_total_transaction_volume, get_user_retention_stats, \
    get_top_users_by_transactions, get_popular_categories, get_database_size

admin_router = Router()


class AdminState(StatesGroup):
    confirm_broadcast = State()


@admin_router.message(Command("maintenance"), AdminFilter())
async def toggle_maintenance(message: Message):
    """Toggle maintenance mode (admin only)"""
    # Toggle maintenance mode
    maintenance_status = await BotSetting.filter_first(BotSetting.key == "maintenance_mode")

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
    maintenance_status = await BotSetting.filter_first(BotSetting.key == "maintenance_mode")

    status = "🔧 Under Maintenance" if str(maintenance_status.value).lower() == "true" else "✅ Running"

    await message.answer(
        f"<b>Bot Status</b>\n\n"
        f"Mode: {status}\n"
        f"Webhook: {'Enabled' if settings.USE_WEBHOOK else 'Polling'}",
        parse_mode="HTML"
    )


@admin_router.message(Command("admin"), AdminFilter())
async def admin_panel(message: Message):
    """Show admin panel with options"""
    await message.delete()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats"),
            InlineKeyboardButton(text="👥 Users", callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton(text="📈 Activity", callback_data="admin_activity"),
            InlineKeyboardButton(text="💾 Database", callback_data="admin_database"),
        ],
        [
            InlineKeyboardButton(text="🔧 Maintenance", callback_data="admin_maintenance"),
            InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast"),
        ],
    ])

    res = "🔐 <b>Admin Panel</b>\n\nSelect an option:"

    try:
        await message.edit_text(
            text=res,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        await message.answer(
            res,
            reply_markup=keyboard,
            parse_mode="HTML"
        )


@admin_router.callback_query(F.data == "admin_broadcast", AdminFilter())
async def show_broadcast_info(callback: CallbackQuery):
    """Show broadcast information"""

    await callback.answer()

    response = (
        get_broadcast_message()
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="« Back", callback_data="admin_back")],
    ])

    await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")


@admin_router.message(Command("broadcast"), AdminFilter())
async def broadcast_message(message: Message, session: AsyncSession, state: FSMContext):
    """Broadcast message to all users"""

    # Get message text (everything after /broadcast)
    text = message.text.replace("/broadcast", "").strip()

    if not text:
        await message.answer(
            "❌ <b>Usage:</b> <code>/broadcast your message here</code>",
            parse_mode="HTML"
        )
        return
    await state.set_state(AdminState.confirm_broadcast)
    await state.update_data(message=text)

    # Confirm broadcast
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes, Send", callback_data=f"broadcast_confirm"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin_back"),
        ]
    ])

    total_users = await get_total_users(session)

    await message.answer(
        get_confirm_broadcast_text(total_users, text),
        reply_markup=keyboard,
        parse_mode="HTML"
    )


@admin_router.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, bot: Bot, session: AsyncSession, state: FSMContext):
    await callback.message.delete()
    broadcast_service = BroadcastService(bot, session)
    data = await state.get_data()
    status = await broadcast_service.send_broadcast(text=data.get("message", "Broadcast failed."))

    success = status["success"]
    if not success:
        await callback.message.answer("Broadcast failed.")
        return
    await callback.message.answer(get_broadcast_sent_text(status))

    await callback.answer()
    await state.clear()


@admin_router.callback_query(F.data == "admin_stats", AdminFilter())
async def show_statistics(callback: CallbackQuery, session: AsyncSession):
    """Show comprehensive statistics"""

    await callback.answer()
    await callback.message.edit_text("⏳ Gathering statistics...", parse_mode="HTML")

    # Gather all stats
    total_users = await get_total_users(session)
    new_today = await get_new_users_today(session)
    active_today = await get_active_users_today(session)
    active_week = await get_active_users_week(session)

    txn_today = await get_transactions_count_today(session)
    txn_total = await get_transactions_count_total(session)

    volumes = await get_total_transaction_volume(session)
    retention = await get_user_retention_stats(session)

    # Calculate averages
    avg_txn_per_user = round(txn_total / total_users, 1) if total_users > 0 else 0

    response = (
        "📊 <b>Bot Statistics</b>\n\n"

        "👥 <b>Users</b>\n"
        f"├ Total: {total_users:,}\n"
        f"├ New today: {new_today:,}\n"
        f"├ Active today: {active_today:,}\n"
        f"├ Active (7d): {active_week:,}\n"
        f"└ Retention: {retention['retention_rate']}%\n\n"

        "💸 <b>Transactions</b>\n"
        f"├ Today: {txn_today:,}\n"
        f"├ Total: {txn_total:,}\n"
        f"└ Avg per user: {avg_txn_per_user}\n\n"

        "💰 <b>Volume Tracked</b>\n"
        f"├ Expenses: {volumes['expense']:,.0f}\n"
        f"└ Income: {volumes['income']:,.0f}\n\n"

        f"🕐 <i>Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_stats")],
        [InlineKeyboardButton(text="« Back", callback_data="admin_back")],
    ])

    await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_users", AdminFilter())
async def show_user_stats(callback: CallbackQuery, session: AsyncSession):
    """Show user-related statistics"""

    await callback.answer()
    await callback.message.edit_text("⏳ Loading user stats...", parse_mode="HTML")

    top_users = await get_top_users_by_transactions(session, limit=10)
    total_users = await get_total_users(session)

    response = f"👥 <b>User Statistics</b>\n\n"
    response += f"<b>Total Users:</b> {total_users:,}\n\n"

    if top_users:
        response += "🏆 <b>Top 10 Most Active Users:</b>\n"
        for idx, user in enumerate(top_users, 1):
            username = f"@{user['username']}" if user['username'] else user['first_name']
            response += f"{idx}. {username} - {user['count']} txns\n"
    else:
        response += "<i>No users yet</i>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_users")],
        [InlineKeyboardButton(text="« Back", callback_data="admin_back")],
    ])

    await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_activity", AdminFilter())
async def show_activity(callback: CallbackQuery, session: AsyncSession):
    """Show activity statistics"""
    await callback.answer()
    await callback.message.edit_text("⏳ Loading activity...", parse_mode="HTML")

    popular_cats = await get_popular_categories(session, limit=10)

    response = "📈 <b>Activity Statistics</b>\n\n"

    if popular_cats:
        response += "🔥 <b>Top 10 Categories:</b>\n"
        for idx, cat in enumerate(popular_cats, 1):
            response += f"{idx}. {cat['icon']} {cat['name']} - {cat['count']} uses\n"
    else:
        response += "<i>No activity yet</i>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_activity")],
        [InlineKeyboardButton(text="« Back", callback_data="admin_back")],
    ])

    await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_database", AdminFilter())
async def show_database_info(callback: CallbackQuery, session: AsyncSession):
    """Show database information"""

    await callback.answer()
    await callback.message.edit_text("⏳ Checking database...", parse_mode="HTML")

    db_size = await get_database_size(session)

    # Count records in each table
    users_count = await get_total_users(session)
    txn_count = await get_transactions_count_total(session)

    result = await session.execute(select(func.count(Category.id)))
    cat_count = result.scalar() or 0

    result = await session.execute(select(func.count(Budget.id)))
    budget_count = result.scalar() or 0

    response = (
        "💾 <b>Database Information</b>\n\n"
        f"<b>Size:</b> {db_size or 'N/A'}\n\n"

        "<b>Records:</b>\n"
        f"├ Users: {users_count:,}\n"
        f"├ Transactions: {txn_count:,}\n"
        f"├ Categories: {cat_count:,}\n"
        f"└ Budgets: {budget_count:,}\n\n"

        f"🕐 <i>Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data="admin_database")],
        [InlineKeyboardButton(text="« Back", callback_data="admin_back")],
    ])

    await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_maintenance", AdminFilter())
async def show_maintenance_options(callback: CallbackQuery):
    """Show maintenance options"""

    await callback.answer()

    status = "🔧 ENABLED" if settings.MAINTENANCE_MODE else "✅ DISABLED"

    response = (
        "🔧 <b>Maintenance Mode</b>\n\n"
        f"<b>Current Status:</b> {status}\n\n"
        "When enabled, all users except admins will see a maintenance message."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔧 Enable Maintenance" if not settings.MAINTENANCE_MODE else "✅ Disable Maintenance",
            callback_data="admin_toggle_maintenance"
        )],
        [InlineKeyboardButton(text="« Back", callback_data="admin_back")],
    ])

    await callback.message.edit_text(response, reply_markup=keyboard, parse_mode="HTML")


@admin_router.callback_query(F.data == "admin_toggle_maintenance", AdminFilter())
async def toggle_maintenance(callback: CallbackQuery):
    """Toggle maintenance mode"""

    # Toggle
    settings.MAINTENANCE_MODE = not settings.MAINTENANCE_MODE

    status = "🔧 ENABLED" if settings.MAINTENANCE_MODE else "✅ DISABLED"

    logger.warning(
        f"Maintenance mode {status} by admin {callback.from_user.id} "
        f"(@{callback.from_user.username})"
    )

    await callback.answer(f"Maintenance mode {status}", show_alert=True)

    # Show updated menu
    await show_maintenance_options(callback)


@admin_router.callback_query(F.data == "admin_back")
async def back_to_admin_panel(callback: CallbackQuery):
    """Go back to main admin panel"""
    await callback.answer()
    await admin_panel(callback.message)


@admin_router.message(Command("stats"), AdminFilter())
async def quick_stats(message: Message, session: AsyncSession):
    """Quick stats command"""
    total_users = await get_total_users(session)
    active_today = await get_active_users_today(session)
    txn_today = await get_transactions_count_today(session)

    response = (
        "📊 <b>Quick Stats</b>\n\n"
        f"👥 Total Users: {total_users:,}\n"
        f"✅ Active Today: {active_today:,}\n"
        f"💸 Transactions Today: {txn_today:,}\n\n"
        f"Use /admin for detailed statistics"
    )

    await message.answer(response, parse_mode="HTML")


@admin_router.message(Command("user_info"), AdminFilter())
async def user_info(message: Message, session: AsyncSession):
    """Get information about a specific user
    Usage: /user_info @username or /user_info 123456789
    """

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Usage:</b>\n"
            "<code>/user_info @username</code> or\n"
            "<code>/user_info 123456789</code>",
            parse_mode="HTML"
        )
        return

    identifier = parts[1].replace("@", "")

    # Try to find user
    if identifier.isdigit():
        # Search by user_id
        result = await session.execute(
            select(User).where(User.user_id == int(identifier))
        )
    else:
        # Search by username
        result = await session.execute(
            select(User).where(User.username == identifier)
        )

    user = result.scalar_one_or_none()

    if not user:
        await message.answer("❌ User not found")
        return

    # Get user's transaction count
    result = await session.execute(
        select(func.count(Transaction.id))
        .where(Transaction.user_id == user.user_id)
    )
    txn_count = result.scalar() or 0

    # Get last transaction date
    result = await session.execute(
        select(func.max(Transaction.created_at))
        .where(Transaction.user_id == user.user_id)
    )
    last_txn = result.scalar()

    response = (
        f"👤 <b>User Information</b>\n\n"
        f"<b>ID:</b> <code>{user.user_id}</code>\n"
        f"<b>Username:</b> @{user.username or 'N/A'}\n"
        f"<b>Name:</b> {user.first_name or 'N/A'}\n"
        f"<b>Currency:</b> {user.currency}\n"
        f"<b>Joined:</b> {user.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"

        f"📊 <b>Activity:</b>\n"
        f"├ Transactions: {txn_count:,}\n"
        f"└ Last Active: {last_txn.strftime('%Y-%m-%d %H:%M') if last_txn else 'Never'}\n"
    )

    await message.answer(response, parse_mode="HTML")


# ==================== EXPORT FUNCTIONS ====================

@admin_router.message(Command("export_users"), AdminFilter())
async def export_users(message: Message, session: AsyncSession):
    """Export all users to CSV"""
    await message.answer("⏳ Exporting users...")

    result = await session.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    if not users:
        await message.answer("❌ No users to export")
        return

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['User ID', 'Username', 'First Name', 'Currency', 'Joined Date'])

    # Data
    for user in users:
        writer.writerow([
            user.user_id,
            user.username or '',
            user.first_name or '',
            user.currency,
            user.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])

    # Send file
    output.seek(0)
    file = BufferedInputFile(
        output.getvalue().encode('utf-8'),
        filename=f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    await message.answer_document(
        file,
        caption=f"📊 Exported {len(users)} users"
    )


# Database Check
@admin_router.message(Command("pingdb"), AdminFilter())
async def cmd_ping_db(msg: Message):
    async with measure("ping_db"):
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
    await msg.answer("Database check done ✅")


@admin_router.message(Command("cache_stats"))
async def cache_stats_handler(message: Message, user_service: UserService):
    """Show cache statistics (admin only)"""
    stats = user_service.get_cache_stats()
    await message.answer(f"📊 Cache Statistics:\n{stats}")
