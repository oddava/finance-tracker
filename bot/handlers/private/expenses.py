from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import User
from bot.keyboards.inline import get_category_keyboard
from bot.services.expense_parser import ExpenseParser
from bot.utils.formatters import format_amount, format_transaction_message
from bot.utils.helpers import get_user_categories, create_transaction, get_category_by_name, get_budget_status, \
    get_transactions_by_period, get_recent_transactions

expense_router = Router()
expense_parser = ExpenseParser()


# FSM States for adding expenses
class ExpenseForm(StatesGroup):
    waiting_for_amount = State()
    waiting_for_category = State()
    waiting_for_description = State()
    confirming = State()


# ==================== NATURAL LANGUAGE EXPENSE LOGGING ====================
@expense_router.message(F.text & ~F.text.startswith('/'))
async def handle_natural_expense(
        message: Message,
        session: AsyncSession,
        state: FSMContext
):
    """
    Handle natural language expense/income input with smart AI fallback
    """
    # Skip if we're in a form state
    current_state = await state.get_state()
    if current_state:
        return

    # Skip greetings and casual chat
    casual_words = ['hi', 'hello', 'hey', 'thanks', 'thank', 'ok', 'okay', 'yes', 'no']
    if message.text.lower().strip() in casual_words:
        return

    user_ = await User.get_or_create(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    user_ = user_[0]

    # Get user categories for better parsing
    categories_ = await get_user_categories(user_.user_id)

    # Show "typing" indicator for AI processing
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Parse the message
    result = await expense_parser.parse(message.text, user_.id, categories_)

    # Debug info for low confidence
    if result['confidence'] < 0.7:
        # Log for debugging
        print(f"Low confidence parse: {result}")

    # Handle based on parsing quality
    if result.get('needs_clarification') or result['confidence'] < 0.4:
        await message.answer(
            "🤔 I couldn't understand that clearly.\n\n"
            "<b>Try formats like:</b>\n"
            "• <code>50k taxi</code>\n"
            "• <code>lunch 25000</code>\n"
            "• <code>bought groceries 120k</code>\n"
            "• <code>received 5k</code> (for income)\n\n"
            "Or use /add for step-by-step entry.",
            parse_mode="HTML"
        )
        return

    # Check if amount is missing
    if not result['amount']:
        await message.answer(
            "💰 <b>I see you want to log something, but how much?</b>\n\n"
            "Please include the amount:\n"
            "• <code>50k</code> or <code>50000</code>\n"
            "• <code>25.5k</code> for decimals",
            parse_mode="HTML"
        )
        return

    # Determine transaction type
    transaction_type = result.get('type', 'expense')
    category_type = 'income' if transaction_type == 'income' else 'expense'

    # Handle income differently (usually no category needed)
    if transaction_type == 'income':
        # For income, category is optional
        income_categories = await get_user_categories(user_.user_id, category_type='income')

        if not result['category'] and income_categories:
            # Show income category selection
            await state.update_data(
                amount=result['amount'],
                description=result['description'],
                transaction_type='income'
            )
            await state.set_state(ExpenseForm.waiting_for_category)

            keyboard_ = get_category_keyboard(income_categories)
            await message.answer(
                f"💰 <b>Income: {format_amount(result['amount'], user_.currency)}</b>\n\n"
                "What type of income?",
                reply_markup=keyboard_,
                parse_mode="HTML"
            )
            return

        # Use default income category if exists
        default_income_cat = income_categories[0] if income_categories else None
        if default_income_cat:
            # Create income transaction
            transaction = await create_transaction(
                user_id=user_.user_id,
                amount=result['amount'],
                category_id=default_income_cat.id,
                transaction_type="income",
                description=result['description'],
                payment_method="bank"
            )

            response = f"✅ <b>Income logged!</b>\n\n"
            response += f"💰 +{format_amount(result['amount'], user_.currency)}\n"
            response += f"📁 {default_income_cat.name}\n"
            if result['description']:
                response += f"📝 {result['description']}"

            await message.answer(response, parse_mode="HTML")
            return

    # For expenses: category is required
    if not result['category']:
        expense_categories = await get_user_categories(user_.id, category_type="expense")

        await state.update_data(
            amount=result['amount'],
            description=result['description'],
            transaction_type='expense'
        )
        await state.set_state(ExpenseForm.waiting_for_category)

        keyboard = get_category_keyboard(expense_categories)
        await message.answer(
            f"💸 <b>Amount: {format_amount(result['amount'], user_.currency)}</b>\n\n"
            f"📝 {result['description']}\n\n"
            "Which category fits best?",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    # Find the category
    category = await get_category_by_name(user_.id, result['category'])

    if not category:
        # Category not found - show selection with suggestion
        expense_categories = await get_user_categories(user_.user_id, category_type="expense")

        await state.update_data(
            amount=result['amount'],
            description=result['description'],
            transaction_type=transaction_type,
            suggested_category=result['category']
        )
        await state.set_state(ExpenseForm.waiting_for_category)

        keyboard = get_category_keyboard(expense_categories)
        await message.answer(
            f"💸 <b>Amount: {format_amount(result['amount'], user_.currency)}</b>\n\n"
            f"📝 {result['description']}\n"
            f"💡 Suggested: <i>{result['category']}</i>\n\n"
            "Select the correct category:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    # Show confidence indicator for medium confidence
    confidence_emoji = ""
    if result['confidence'] < 0.75:
        confidence_emoji = " 🤔"
    elif result['method'] == 'ai_enhanced':
        confidence_emoji = " 🤖"

    # Create transaction
    transaction = await create_transaction(
        user_id=user_.user_id,
        amount=result['amount'],
        category_id=category.id,
        transaction_type=transaction_type,
        description=result['description'],
        payment_method="cash"
    )

    # Check budget status for expenses
    budget_info = ""
    if transaction_type == 'expense':
        budget_status = await get_budget_status(session, user_.id, category.id)

        if budget_status:
            percentage = budget_status['percentage']
            spent = budget_status['spent']
            budget_amount = budget_status['budget'].amount

            if budget_status['is_exceeded']:
                budget_info += f"\n\n⚠️ Budget exceeded!\n"
                budget_info += f"Spent: {format_amount(spent, user_.currency)} / {format_amount(budget_amount, user_.currency)}"
            elif budget_status['is_warning']:
                budget_info += f"\n\n⚡ Budget warning: {percentage}%\n"
                budget_info += f"Spent: {format_amount(spent, user_.currency)} / {format_amount(budget_amount, user_.currency)}"
            else:
                budget_info += f"\n\n✅ Budget: {format_amount(spent, user_.currency)} / {format_amount(budget_amount, user_.currency)} ({percentage}%)"

            await message.answer(budget_info)

                                         # ==================== CATEGORY SELECTION CALLBACK ====================

@expense_router.callback_query(F.data.startswith("cat_"), ExpenseForm.waiting_for_category)
async def category_selected(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Handle category selection"""
    category_id = int(callback.data.split("_")[1])
    data = await state.get_data()

    user = await User.get_or_create(
        user_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name
    )
    user = user[0]

    # Get category
    categories = await get_user_categories(user.user_id)
    category = next((c for c in categories if c.id == category_id), None)

    if not category:
        await callback.answer("Category not found", show_alert=True)
        return

    # Create transaction
    transaction = await create_transaction(
        user_id=user.user_id,
        amount=data['amount'],
        category_id=category.id,
        transaction_type="expense",
        description=data.get('description', ''),
        payment_method="cash"
    )

    # Clear state
    await state.clear()

    # Format response
    response = format_transaction_message(transaction, category, user.currency)

    # Check budget
    budget_status = await get_budget_status(session, user.user_id, category.id)
    if budget_status:
        percentage = budget_status['percentage']
        spent = budget_status['spent']
        budget_amount = budget_status['budget'].amount

        if budget_status['is_exceeded']:
            response += f"\n\n⚠️ Budget exceeded!\n"
            response += f"Spent: {format_amount(spent, user.currency)} / {format_amount(budget_amount, user.currency)}"
        elif budget_status['is_warning']:
            response += f"\n\n⚡ Budget warning: {percentage}%\n"
            response += f"Spent: {format_amount(spent, user.currency)} / {format_amount(budget_amount, user.currency)}"
        else:
            response += f"\n\n✅ Budget: {percentage}%"

    await callback.message.edit_text(response)
    await callback.answer()

#
# # ==================== MANUAL ADD COMMAND ====================
#
# @expense_router.message(Command("add"))
# async def cmd_add_expense(message: Message, state: FSMContext):
#     """Start manual expense addition flow"""
#     await state.set_state(ExpenseForm.waiting_for_amount)
#     await message.answer(
#         "💰 Let's add an expense!\n\n"
#         "How much did you spend?\n"
#         "Example: 50000 or 50k\n\n"
#         "Send /cancel to abort."
#     )
#
#
# @expense_router.message(ExpenseForm.waiting_for_amount)
# async def process_amount(message: Message, state: FSMContext, session: AsyncSession):
#     """Process amount input"""
#     if message.text == "/cancel":
#         await state.clear()
#         await message.answer("❌ Cancelled.")
#         return
#
#     # Parse amount
#     text = message.text.lower().replace(',', '.')
#     amount = None
#
#     try:
#         # Handle "k" notation (50k = 50000)
#         if 'k' in text:
#             amount = float(text.replace('k', '').strip()) * 1000
#         else:
#             amount = float(text.strip())
#     except ValueError:
#         await message.answer(
#             "❌ Invalid amount. Please enter a number.\n"
#             "Example: 50000 or 50k"
#         )
#         return
#
#     if amount <= 0:
#         await message.answer("❌ Amount must be greater than zero.")
#         return
#
#     # Store amount and ask for category
#     await state.update_data(amount=amount)
#     await state.set_state(ExpenseForm.waiting_for_category)
#
#     user = await User.get_or_create(
#         user_id=message.from_user.id,
#         username=message.from_user.username,
#         first_name=message.from_user.first_name
#     )
#     user = user[0]
# user = user[1
#
#     categories = await crud.get_user_categories(session, user.id, category_type="expense")
#     keyboard = get_category_keyboard(categories)
#
#     await message.answer(
#         f"✅ Amount: {format_amount(amount, user.currency)}\n\n"
#         "Now select a category:",
#         reply_markup=keyboard
#     )
#
#
# @expense_router.callback_query(F.data.startswith("cat_"), ExpenseForm.waiting_for_amount)
# async def category_selected_manual(
#         callback: CallbackQuery,
#         session: AsyncSession,
#         state: FSMContext
# ):
#     """Handle category selection in manual flow"""
#     category_id = int(callback.data.split("_")[1])
#     data = await state.get_data()
#
#     await state.update_data(category_id=category_id)
#     await state.set_state(ExpenseForm.waiting_for_description)
#
#     user = await crud.get_or_create_user(
#         session,
#         telegram_id=callback.from_user.id
#     )
#
#     categories = await get_user_categories(session, user.user_id)
#     category = next((c for c in categories if c.id == category_id), None)
#
#     await callback.message.edit_text(
#         f"✅ Amount: {format_amount(data['amount'], user.currency)}\n"
#         f"✅ Category: {category.icon_emoji} {category.name}\n\n"
#         "Add a description? (optional)\n"
#         "Or send /skip to finish."
#     )
#     await callback.answer()
#
#
# @expense_router.message(ExpenseForm.waiting_for_description)
# async def process_description(
#         message: Message,
#         session: AsyncSession,
#         state: FSMContext
# ):
#     """Process description and save transaction"""
#     if message.text == "/cancel":
#         await state.clear()
#         await message.answer("❌ Cancelled.")
#         return
#
#     data = await state.get_data()
#     description = "" if message.text == "/skip" else message.text
#
#     user = await crud.get_or_create_user(
#         session,
#         telegram_id=message.from_user.id
#     )
#
#     # Create transaction
#     transaction = await crud.create_transaction(
#         session=session,
#         user_id=user.id,
#         amount=data['amount'],
#         category_id=data['category_id'],
#         transaction_type="expense",
#         description=description,
#         payment_method="cash"
#     )
#
#     # Get category for display
#     categories = await get_user_categories(session, user.user_id)
#     category = next((c for c in categories if c.id == data['category_id']), None)
#
#     await state.clear()
#
#     response = "✅ Expense added!\n\n"
#     response += format_transaction_message(transaction, category, user.currency)
#
#     # Check budget
#     budget_status = await crud.get_budget_status(session, user.id, category.id)
#     if budget_status:
#         percentage = budget_status['percentage']
#         if budget_status['is_exceeded']:
#             response += f"\n\n⚠️ Budget exceeded! ({percentage}%)"
#         elif budget_status['is_warning']:
#             response += f"\n\n⚡ Warning: {percentage}% of budget used"
#
#     await message.answer(response)


# ==================== TODAY'S SUMMARY ====================

@expense_router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession):
    """Show today's expenses summary"""
    user = await User.get_or_create(user_id=message.from_user.id, username=message.from_user.username)
    user = user[0]

    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)

    transactions = await get_transactions_by_period(
        session, user.user_id, start_of_day, end_of_day, transaction_type="expense"
    )

    if not transactions:
        await message.answer("📊 No expenses recorded today.")
        return

    total = sum(t.amount for t in transactions)

    response = f"📊 <b>Today's Expenses</b>\n\n"
    response += f"💸 Total: {format_amount(total, user.currency)}\n"
    response += f"📝 Transactions: {len(transactions)}\n\n"

    # Group by category
    by_category = {}
    for t in transactions:
        cat_name = t.category.name
        if cat_name not in by_category:
            by_category[cat_name] = {
                'emoji': t.category.icon_emoji,
                'amount': 0,
                'count': 0
            }
        by_category[cat_name]['amount'] += t.amount
        by_category[cat_name]['count'] += 1

    response += "<b>By Category:</b>\n"
    for cat_name, data in sorted(by_category.items(), key=lambda x: x[1]['amount'], reverse=True):
        percentage = (data['amount'] / total * 100) if total > 0 else 0
        response += f"{data['emoji']} {cat_name}: {format_amount(data['amount'], user.currency)} ({percentage:.0f}%)\n"

    response += "\n<b>Recent transactions:</b>\n"
    for t in transactions[-5:]:
        response += f"• {t.category.icon_emoji} {format_amount(t.amount, user.currency)}"
        if t.description:
            response += f" - {t.description}"
        response += "\n"

    await message.answer(response, parse_mode="HTML")


# ==================== RECENT TRANSACTIONS ====================

@expense_router.message(Command("recent"))
async def cmd_recent(message: Message, session: AsyncSession):
    """Show recent transactions"""
    user = await User.get_or_create(user_id=message.from_user.id, username=message.from_user.username)
    user = user[0]

    transactions = await get_recent_transactions(session, user.user_id, limit=10)

    if not transactions:
        await message.answer("📊 No transactions yet. Start by logging your first expense!")
        return

    response = "📋 <b>Recent Transactions</b>\n\n"

    for t in transactions:
        date_str = t.date.strftime("%d %b, %H:%M")
        type_emoji = "💸" if t.type == "expense" else "💰"

        response += f"{type_emoji} {t.category.icon_emoji} <b>{format_amount(t.amount, user.currency)}</b>\n"
        response += f"   {t.category.name}"
        if t.description:
            response += f" • {t.description}"
        response += f"\n   <i>{date_str}</i>\n\n"

    await message.answer(response, parse_mode="HTML")


# ==================== CANCEL COMMAND ====================

@expense_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current operation"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Nothing to cancel.")
        return

    await state.clear()
    await message.answer("❌ Operation cancelled.")