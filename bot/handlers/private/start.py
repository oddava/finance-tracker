"""
Start command and main menu handlers
"""
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import User
from bot.keyboards.inline import currency_choice_ikm
from bot.utils.helpers import get_monthly_summary, create_default_categories

from loguru import logger

from bot.utils.perf import measure

from aiogram.utils.i18n import gettext as _

start_router = Router()


@start_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Handle /start command - welcome new users"""

    async with measure("start_handler"):
        logger.info(f"User {message.from_user.id} has started the bot.")

        user_data = message.from_user.model_dump(include={'first_name', 'language_code', 'username'})
        async with measure("get_user_data"):
            user, created = await User.get_or_create(
                user_id=message.from_user.id,
                defaults=dict(user_data)
            )

        if not created:
            await message.answer(
                text=_("What would you like to do?\n\n"
                       "<b>Quick Commands:</b>\n"
                       "• Just type: <code>50k taxi</code>\n"
                       "• /today - Today's summary\n"
                       "• /recent - Recent transactions\n"
                       "• /help - About this bot"),
                parse_mode="HTML"
            )
            return

        await message.answer(
            _("Welcome!\n💱 <b>First, let's set your currency:</b>\n\n"
              "Select your preferred currency:"),
            reply_markup=currency_choice_ikm(),
            parse_mode="HTML"
        )
        await create_default_categories(session, message.from_user.id)


@start_router.callback_query(F.data.startswith("currency_set_"))
async def currency_selected(callback: CallbackQuery):
    """Handle currency selection"""

    currency = callback.data.split("_")[2]

    user = await User.get(callback.from_user.id)
    user.currency = currency
    await user.save()

    await callback.message.edit_text(
        _(f"✅ Currency set to: {currency}\n\n"
          "Perfect! You're all set up.\n\n"
          "<b>Try your first expense:</b>\n"
          "• Example: <code>50k taxi</code>\n"
          "Let's get started! 🚀"),
        parse_mode="HTML"
    )

    await callback.answer()


@start_router.message(Command("help"))
async def cmd_help(message: Message):
    """Show help message"""
    await message.answer(_(
        "❓ <b>How to use the bot</b>\n\n"

        "<b>📝 Logging Expenses:</b>\n"
        "• Example: <code>50k taxi</code>\n"
        "• Example: <code>lunch 25000</code>\n"
        "• Example: <code>spent 150 on groceries</code>\n"

        "<b>📊 View Reports:</b>\n"
        "• /today - Today's expenses\n"
        "• /week [soon] - This week's summary\n"
        "• /month [soon] - Monthly breakdown\n"
        "• /recent - Last 10 transactions\n\n"

        "<b>🎯 Budgets [soon]:</b>\n"
        "• /budget - Set/view budgets\n"
        "• /budgets - All budgets status\n\n"

        "<b>⚙️ Settings [soon]:</b>\n"
        "• /settings - Change preferences\n"
        "• /currency - Change currency\n"
        "• /categories - Manage categories\n\n"

        "<b>📈 Analytics [soon]:</b>\n"
        "• /insights - AI-powered insights\n"
        "• /compare - Compare periods\n"
        "• /export - Export data to Excel\n\n"

        "<b>📚 Other:</b>\n"
        "• /about - About the bot\n"
        "• /feedback - Report issues\n\n"
    ), parse_mode="HTML")


@start_router.message(Command("about"))
async def cmd_about(message: Message, session: AsyncSession):
    """Show bot information and user stats"""

    async with measure("about_handler"):
        user, created = await User.get_or_create(
            user_id=message.from_user.id
        )

        # Get user statistics
        current_month = datetime.now()
        monthly_summary = await get_monthly_summary(
            session,
            user.user_id,
            current_month.year,
            current_month.month
        )

        await message.answer(_(
            "ℹ️ <b>About Finance Tracker Bot</b>\n\n"

            "🤖 Smart personal finance tracking made easy!\n\n"

            "<b>Your Stats:</b>\n"
            "📅 Member since: {joined_date}\n"
            "💰 Currency: {currency}\n"
            "📝 This month: {monthly_transactions} transactions\n"
            "💸 Total spent: {total_spent} {currency}\n\n"

            "<b>Features:</b>\n"
            "✅ Natural language expense logging\n"
            "✅ Budget tracking & alerts\n"
            "✅ Smart insights & analytics\n"
            "✅ Visual reports & charts\n"
            "✅ Multiple currencies support\n"
            "✅ Data export (Excel/CSV)\n\n"

            "Made with ❤️\n"
            "Version: 1.0.0"
        ).format(joined_date=user.created_at.strftime('%d %b %Y'), currency=user.currency,
                 monthly_transactions=monthly_summary['transaction_count'],
                 total_spent=monthly_summary['total_expenses']), parse_mode="HTML")


@start_router.message(Command("feedback"))
async def cmd_feedback(message: Message):
    """Show feedback/support information"""

    await message.answer(_(
        "💬 <b>Feedback & Support</b>\n\n"

        "We'd love to hear from you!\n\n"

        "📧 <b>Contact:</b>\n"
        "• Telegram: @notJony\n\n"

        "🐛 <b>Report Issues:</b>\n"
        "Found a bug? Let us know!\n\n"

        "⭐ <b>Feature Requests:</b>\n"
        "Have an idea? We're listening!\n\n"

        "🌟 <b>Rate Us:</b>\n"
        "Enjoying the bot? Share with friends!"
    ), parse_mode="HTML")
