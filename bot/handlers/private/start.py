"""
Start command and main menu handlers
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import User
from bot.keyboards.inline import currency_choice_ikm
from bot.utils.helpers import get_monthly_summary, create_default_categories

start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """Handle /start command - welcome new users"""

    # Get or create user
    user = await User.get_or_create(
        user_id=message.from_user.id,
        defaults={
            "first_name": message.from_user.first_name,
            "language_code": message.from_user.language_code,
            "username": message.from_user.username,
        }
    )

    # Check if this is a new user
    is_new_user = user[1]

    if is_new_user:
        await create_default_categories(session, message.from_user.id)
        await message.answer("Welcome!", parse_mode="HTML")

        # Ask for currency preference
        await message.answer(
            "💱 <b>First, let's set your currency:</b>\n\n"
            "Select your preferred currency:",
            reply_markup=currency_choice_ikm(),
            parse_mode="HTML"
        )
        await create_default_categories(session, message.from_user.id)
    else:
        # Returning user - show menu
        await show_main_menu(message)


@start_router.callback_query(F.data.startswith("currency_set_"))
async def currency_selected(callback: CallbackQuery, session: AsyncSession):
    """Handle currency selection"""

    currency = callback.data.split("_")[2]

    # Update user currency
    user = await User.get(callback.from_user.id)
    user.currency = currency
    await user.save()

    await callback.message.edit_text(
        f"✅ Currency set to: {currency}\n\n"
        "Perfect! You're all set up.\n\n"
        "<b>Try your first expense:</b>\n"
        "• Type: <code>50k taxi</code>\n"
        "• Or use: /add\n\n"
        "Let's get started! 🚀",
        parse_mode="HTML"
    )

    await callback.answer()


@start_router.message(Command("menu"))
async def cmd_menu(message: Message, session: AsyncSession):
    """Show main menu"""
    await show_main_menu(message)


async def show_main_menu(message: Message):
    """Display main menu with all options"""

    menu_text = (
        "🏠 <b>Main Menu</b>\n\n"
        "What would you like to do?\n\n"
        "<b>Quick Commands:</b>\n"
        "• Just type: <code>50k taxi</code>\n"
        "• /add - Add expense step-by-step\n"
        "• /today - Today's summary\n"
        "• /month - Monthly report\n"
        "• /recent - Recent transactions\n"
        "• /help - Get help"
    )

    await message.answer(
        menu_text,
        # reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )


@start_router.callback_query(F.data == "menu_main")
async def menu_main_callback(callback: CallbackQuery):
    """Handle main menu button"""
    menu_text = (
        "🏠 <b>Main Menu</b>\n\n"
        "What would you like to do?"
    )

    await callback.message.edit_text(
        menu_text,
        # reply_markup=get_main_menu_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@start_router.callback_query(F.data == "menu_add_expense")
async def menu_add_expense(callback: CallbackQuery):
    """Redirect to add expense"""
    await callback.message.answer(
        "💸 <b>Add Expense</b>\n\n"
        "How much did you spend?\n"
        "Example: 50000 or 50k\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML"
    )
    await callback.answer()


@start_router.message(Command("help"))
async def cmd_help(message: Message):
    """Show help message"""

    help_text = (
        "❓ <b>How to Use Finance Tracker Bot</b>\n\n"

        "<b>📝 Logging Expenses:</b>\n"
        "• Natural: <code>50k taxi</code>\n"
        "• Natural: <code>lunch 25000</code>\n"
        "• Natural: <code>spent 150 on groceries</code>\n"
        "• Manual: /add (step-by-step)\n\n"

        "<b>📊 View Reports:</b>\n"
        "• /today - Today's expenses\n"
        "• /week - This week's summary\n"
        "• /month - Monthly breakdown\n"
        "• /recent - Last 10 transactions\n\n"

        "<b>🎯 Budgets:</b>\n"
        "• /budget - Set/view budgets\n"
        "• /budgets - All budgets status\n\n"

        "<b>💰 Income:</b>\n"
        "• /income - Add income\n\n"

        "<b>⚙️ Settings:</b>\n"
        "• /settings - Change preferences\n"
        "• /currency - Change currency\n"
        "• /categories - Manage categories\n\n"

        "<b>📈 Analytics:</b>\n"
        "• /insights - AI-powered insights\n"
        "• /compare - Compare periods\n"
        "• /export - Export data to Excel\n\n"

        "<b>Other:</b>\n"
        "• /menu - Show main menu\n"
        "• /cancel - Cancel current operation\n"
        "• /help - Show this message\n\n"

        "💡 <b>Pro Tip:</b> Just type naturally! The bot understands:\n"
        "\"50k taxi\", \"bought groceries 120\", \"coffee 15000\""
    )

    await message.answer(help_text, parse_mode="HTML")


@start_router.message(Command("about"))
async def cmd_about(message: Message, session: AsyncSession):
    """Show bot information and user stats"""

    user = await User.get_or_create(
        user_id=message.from_user.id
    )
    user = user[0]

    # Get user statistics
    from datetime import datetime
    current_month = datetime.now()
    monthly_summary = await get_monthly_summary(
        session,
        user.id,
        current_month.year,
        current_month.month
    )

    about_text = (
        "ℹ️ <b>About Finance Tracker Bot</b>\n\n"

        "🤖 Smart personal finance tracking made easy!\n\n"

        "<b>Your Stats:</b>\n"
        f"📅 Member since: {user.created_at.strftime('%d %b %Y')}\n"
        f"💰 Currency: {user.currency}\n"
        f"📝 This month: {monthly_summary['transaction_count']} transactions\n"
        f"💸 Total spent: {monthly_summary['total_expenses']:,.0f} {user.currency}\n\n"

        "<b>Features:</b>\n"
        "✅ Natural language expense logging\n"
        "✅ Budget tracking & alerts\n"
        "✅ Smart insights & analytics\n"
        "✅ Visual reports & charts\n"
        "✅ Multiple currencies support\n"
        "✅ Data export (Excel/CSV)\n\n"

        "Made with ❤️ using Aiogram & OpenAI\n"
        "Version: 1.0.0"
    )

    await message.answer(about_text, parse_mode="HTML")


@start_router.message(Command("feedback"))
async def cmd_feedback(message: Message):
    """Show feedback/support information"""

    feedback_text = (
        "💬 <b>Feedback & Support</b>\n\n"

        "We'd love to hear from you!\n\n"

        "📧 <b>Contact:</b>\n"
        "• Email: support@financebot.com\n"
        "• Telegram: @YourSupportBot\n\n"

        "🐛 <b>Report Issues:</b>\n"
        "Found a bug? Let us know!\n\n"

        "⭐ <b>Feature Requests:</b>\n"
        "Have an idea? We're listening!\n\n"

        "🌟 <b>Rate Us:</b>\n"
        "Enjoying the bot? Share with friends!"
    )

    await message.answer(feedback_text, parse_mode="HTML")


@start_router.message(F.text.lower().in_([
    "hi", "hello", "hey", "привет", "salom"
]))
async def handle_greetings(message: Message):
    """Handle casual greetings"""

    greetings = [
        "👋 Hello! Ready to track some expenses?",
        "Hi there! 💰 How can I help you today?",
        "Hey! 👋 Let's manage your finances!",
        "Hello! Start by telling me what you spent. 😊"
    ]

    import random
    await message.answer(random.choice(greetings))


@start_router.message(F.text.lower().in_([
    "thanks", "thank you", "thx", "спасибо", "rahmat"
]))
async def handle_thanks(message: Message):
    """Handle thank you messages"""

    responses = [
        "You're welcome! 😊",
        "Happy to help! 💙",
        "Anytime! Keep tracking! 💪",
        "My pleasure! 🎉"
    ]

    import random
    await message.answer(random.choice(responses))