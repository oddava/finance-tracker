"""
Start command and main menu handlers
"""
import random
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.state import StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import User
from bot.keyboards.inline import currency_choice_ikm
from bot.utils.helpers import get_monthly_summary, create_default_categories

from loguru import logger

from bot.utils.text import get_help_text, get_about_text, get_menu_text, get_feedback_text

start_router = Router()

@start_router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession) -> None:
    """Handle /start command - welcome new users"""
    logger.info(f"User {message.from_user.id} has started the bot.")

    user_data = message.from_user.model_dump(include={'first_name', 'language_code', 'username'})
    user, created = await User.get_or_create(
        user_id=message.from_user.id,
        defaults=dict(user_data)
    )

    if not created:
        menu_text = get_menu_text()
        await message.answer(
            text=menu_text,
            parse_mode="HTML"
        )
        return

    await message.answer("Welcome!", parse_mode="HTML")

    await message.answer(
        "💱 <b>First, let's set your currency:</b>\n\n"
        "Select your preferred currency:",
        reply_markup=currency_choice_ikm(),
        parse_mode="HTML"
    )
    await create_default_categories(session, message.from_user.id)


@start_router.callback_query(F.data.startswith("currency_set_"))
async def currency_selected(callback: CallbackQuery):
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
        "• Example: <code>50k taxi</code>\n"
        "Let's get started! 🚀",
        parse_mode="HTML"
    )

    await callback.answer()

@start_router.message(Command("help"))
async def cmd_help(message: Message):
    """Show help message"""
    help_text = get_help_text()

    await message.answer(help_text, parse_mode="HTML")


@start_router.message(Command("about"))
async def cmd_about(message: Message, session: AsyncSession):
    """Show bot information and user stats"""

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

    about_text = get_about_text(user, monthly_summary)

    await message.answer(about_text, parse_mode="HTML")


@start_router.message(Command("feedback"))
async def cmd_feedback(message: Message):
    """Show feedback/support information"""

    feedback_text = get_feedback_text()

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

    await message.answer(random.choice(responses))