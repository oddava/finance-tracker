from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State

from bot.database import User, Category
from bot.keyboards.inline import get_category_keyboard
from bot.services.budget_service import BudgetService
from bot.services.category_service import CategoryService
from bot.services.expense_parser import ExpenseParser
from bot.services.transaction_service import TransactionService
from bot.utils.formatters import format_amount
from bot.utils.helpers import get_recent_transactions, get_transactions_today, to_user_timezone
from aiogram.utils.i18n import gettext as _

expense_router = Router()
expense_parser = ExpenseParser()

"""
Production-ready expense handler with improved structure and UX
"""
from typing import Optional, Dict, Any
from aiogram import F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

# Constants
CASUAL_WORDS = {'hi', 'hello', 'hey', 'thanks', 'thank', 'ok', 'okay', 'yes', 'no', 'bye'}
MIN_CONFIDENCE_THRESHOLD = 0.4
AUTO_CREATE_THRESHOLD = 0.75


class ExpenseForm(StatesGroup):
    waiting_for_category = State()
    waiting_for_expense = State()


class ExpenseHandler:
    """Handles expense/income processing with better separation of concerns"""

    def __init__(
            self,
            session: AsyncSession,
            user: User,
            message: Message,
            state: FSMContext
    ):
        self.session = session
        self.user = user
        self.message = message
        self.state = state
        self.transaction_service = TransactionService(session)
        self.budget_service = BudgetService(session)
        self.category_service = CategoryService(session)

    async def process_natural_input(self, text: str) -> bool:
        """
        Process natural language input
        Returns True if handled, False otherwise
        """
        try:
            if self._should_skip_input(text):
                logger.info(f"Skipping invalid input: {text[:50]}")
                return True
            # Get user categories for better parsing context
            categories = await self.category_service.get_user_categories(
                self.user.user_id
            )

            # Show typing indicator
            await self.message.bot.send_chat_action(
                self.message.chat.id,
                "typing"
            )

            # Parse the input
            try:
                parse_result = await expense_parser.parse(text, self.user.id, categories)
            except Exception as e:
                logger.exception(f"Parsing failed for input '{text}': {e}")
                await self.message.answer(
                    _("❌ <b>Could not understand your input</b>\n\n"
                      "Please try again or use /add for manual entry."),
                    parse_mode="HTML"
                )
                return True

            logger.info(
                f"Parse result for user {self.user.user_id}: "
                f"confidence={parse_result['confidence']}, "
                f"method={parse_result.get('method', 'unknown')}"
                f"is_multiple={parse_result.get('is_multiple', False)}, "
            )

            if parse_result.get('is_multiple'):
                await self._handle_multiple_expenses(parse_result)
                return True

            # Handle low confidence
            if parse_result['confidence'] < MIN_CONFIDENCE_THRESHOLD:
                await self._send_help_message(parse_result)
                return True

            # Route to appropriate handler
            type = parse_result.get('type', 'expense')

            if type == 'income':
                await self._handle_income(parse_result)
            else:
                await self._handle_expense(parse_result)
            return True

        except Exception as e:
            logger.exception(f"Error processing natural input: {e}")
            await self.message.answer(
                _("❌ <b>Something went wrong</b>\n\n"
                  "Please try again later."),
                parse_mode="HTML"
            )
            return True

    async def _handle_multiple_expenses(self, parse_result: Dict[str, Any]):
        """
        Handle multiple expenses in one message
        Example: "10k food, 5k taxi, 20k groceries"

        CHANGE #3: NEW METHOD - Handles multiple transactions
        """
        transactions = parse_result.get('transactions', [])

        if not transactions:
            await self.message.answer(
                _("🤔 I detected multiple expenses but couldn't parse them clearly.\n\n"
                  "Try separating them with commas:\n"
                  "<code>10k food, 5k taxi, 20k groceries</code>"),
                parse_mode="HTML"
            )
            return

        logger.info(f"Processing {len(transactions)} transactions")

        # Separate transactions by whether they need category selection
        auto_create = []  # High confidence with category
        need_category = []  # Need user to select category

        for idx, txn in enumerate(transactions):
            amount = txn.get('amount')
            category_name = txn.get('category')
            description = txn.get('description', '')
            confidence = txn.get('confidence', 0)
            type_ = txn.get('type')

            # Find category
            category = None
            if category_name:
                category = await self.category_service.get_category_by_name(
                    self.user.user_id,
                    category_name,
                    category_type=type_
                )

            # Can auto-create if category found and good confidence
            if category and confidence >= AUTO_CREATE_THRESHOLD:
                auto_create.append({
                    'amount': amount,
                    'category': category,
                    'description': description,
                    'confidence': confidence,
                    'type': type_,
                })
            else:
                need_category.append({
                    'amount': amount,
                    'description': description,
                    'suggested_category': category_name,
                    'confidence': confidence,
                    'index': idx,
                    'type': type_,
                })

        # Create transactions that don't need confirmation
        created_count = 0
        total_amount = 0
        budget_warnings = []

        for txn_data in auto_create:
            try:
                await self.transaction_service.create_transaction(
                    user_id=self.user.user_id,
                    amount=txn_data['amount'],
                    category_id=txn_data['category'].id,
                    transaction_type=txn_data['type'],
                    description=txn_data['description'],
                    payment_method='cash'
                )
                created_count += 1
                if txn_data['type'] != 'income':
                    total_amount += txn_data['amount']

                # Check budget
                budget_info = await self._get_budget_info(
                    txn_data['category'].id,
                    txn_data['amount']
                )
                if budget_info and ('exceeded' in budget_info or 'warning' in budget_info):
                    budget_warnings.append(
                        f"• {txn_data['category'].name}: {budget_info}"
                    )
            except Exception as e:
                logger.error(f"Failed to create transaction: {e}")

        # Build response message
        response = ""

        if created_count > 0:
            confidence_indicator = " ✨" if len(auto_create) == len(transactions) else ""
            response += (
                _("✅ <b>{created_count} expense(s) logged!{confidence_indicator}</b>\n\n"
                  "💸 Total: -{total_amount}\n\n").format(created_count=created_count,
                                                         confidence_indicator=confidence_indicator,
                                                         total_amount=format_amount(total_amount, self.user.currency))
            )

            # List created transactions
            for txn_data in auto_create:
                response += (
                    f"• {format_amount(txn_data['amount'], self.user.currency)} "
                    f"- {txn_data['category'].name}"
                )
                if txn_data['description']:
                    response += f" ({txn_data['description']})"
                response += "\n"

            # Add budget warnings if any
            if budget_warnings:
                response += "\n⚠️ <b>Budget Alerts:</b>\n"
                response += "\n".join(budget_warnings)

        # Handle transactions that need category selection
        if need_category:
            if created_count > 0:
                await self.message.answer(response, parse_mode="HTML")

            # Process first unclear transaction
            first_unclear = need_category[0]
            await self._request_category_selection(
                amount=first_unclear['amount'],
                description=first_unclear['description'],
                type=first_unclear['type'],
                suggested_category=first_unclear['suggested_category'],
                remaining_transactions=need_category[1:]
            )
        else:
            # All transactions created successfully
            await self.message.answer(response, parse_mode="HTML")

    async def _handle_expense(self, parse_result: Dict[str, Any]):
        """Handle expense transaction"""
        amount = parse_result['amount']
        description = parse_result.get('description', '')
        category_name = parse_result.get('category')
        confidence = parse_result['confidence']

        # Find category
        category = None
        if category_name:
            category = await self.category_service.get_category_by_name(
                self.user.user_id,
                category_name,
                category_type='expense'
            )

        # High confidence + category found = auto-create
        if category and confidence >= AUTO_CREATE_THRESHOLD:
            await self._create_expense_transaction(
                amount=amount,
                category=category,
                description=description,
                confidence=confidence
            )
            return

        # Need category selection
        await self._request_category_selection(
            amount=amount,
            description=description,
            type='expense',
            suggested_category=category_name,
        )

    async def _handle_income(self, parse_result: Dict[str, Any]):
        """Handle income transaction"""
        amount = parse_result['amount']
        description = parse_result.get('description', '')
        category_name = parse_result.get('category')

        # Get income categories
        income_categories = await self.category_service.get_user_categories(
            self.user.user_id,
            category_type='income'
        )

        if not income_categories:
            await self.message.answer(
                _("⚠️ <b>No income categories found</b>\n\n"
                  "Please create an income category first using /categories"),
                parse_mode="HTML"
            )
            return

        # Find specific category
        category = None
        if category_name:
            category = await self.category_service.get_category_by_name(
                self.user.user_id,
                category_name,
                category_type='income'
            )

        # Auto-select if only one income category
        if not category and len(income_categories) == 1:
            category = income_categories[0]

        # Create transaction if category found
        if category:
            await self._create_income_transaction(
                amount=amount,
                category=category,
                description=description
            )
            return

        # Need category selection
        await self._request_category_selection(
            amount=amount,
            description=description,
            type='income',
            suggested_category=category_name
        )

    async def _create_expense_transaction(
            self,
            amount: float,
            category: Category,
            description: str,
            confidence: float
    ):
        """Create expense transaction and show result"""
        try:
            # Create transaction
            await self.transaction_service.create_transaction(
                user_id=self.user.user_id,
                amount=amount,
                category_id=category.id,
                transaction_type='expense',
                description=description,
                payment_method='cash'
            )

            # Format base response
            confidence_indicator = self._get_confidence_indicator(confidence)
            response = (
                f"✅ <b>{_('Expense logged!')}{confidence_indicator}</b>\n\n"
                f"💸 -{format_amount(amount, self.user.currency)}\n"
                f"📁 {category.name}\n"
            )

            if description:
                response += f"📝 {description}\n"

            # Check budget status
            budget_info = await self._get_budget_info(category.id, amount)
            if budget_info:
                response += f"\n{budget_info}"

            await self.message.answer(response, parse_mode="HTML")

        except Exception as e:
            logger.exception(f"Error creating expense transaction: {e}")
            await self.message.answer(
                _("❌ Failed to save expense. Please try again."),
                parse_mode="HTML"
            )

    async def _create_income_transaction(
            self,
            amount: float,
            category: Category,
            description: str
    ):
        """Create income transaction and show result"""
        try:
            transaction = await self.transaction_service.create_transaction(
                user_id=self.user.user_id,
                amount=amount,
                category_id=category.id,
                transaction_type='income',
                description=description,
                payment_method='bank'
            )

            response = (
                f"✅ <b>{_('Income logged!')}</b>\n\n"
                f"💰 +{format_amount(amount, self.user.currency)}\n"
                f"📁 {category.name}\n"
            )

            if description:
                response += f"📝 {description}"

            await self.message.answer(response, parse_mode="HTML")

        except Exception as e:
            logger.exception(f"Error creating income transaction: {e}")
            await self.message.answer(
                _("❌ Failed to save income. Please try again."),
                parse_mode="HTML"
            )

    async def _request_category_selection(
            self,
            amount: float,
            description: str,
            type: str,
            suggested_category: Optional[str] = None,
            remaining_transactions=None
    ):
        """Request user to select category"""
        # Save state data
        state_data = {
            'amount': amount,
            'description': description,
            'transaction_type': type,
            'suggested_category': suggested_category
        }

        if remaining_transactions:
            state_data['remaining_transactions'] = remaining_transactions

        await self.state.update_data(**state_data)
        await self.state.set_state(ExpenseForm.waiting_for_category)

        # Get categories
        categories = await self.category_service.get_user_categories(
            self.user.user_id,
            category_type=type
        )

        if not categories:
            await self.message.answer(
                _(f"⚠️ <b>No {type} categories found</b>\n\n"
                  f"Please create categories first using /categories"),
                parse_mode="HTML"
            )
            await self.state.clear()
            return

        # Build message
        emoji = "💸" if type == "expense" else "💰"
        action = _('Expense') if type == "expense" else _("Income")

        message_text = (
            f"{emoji} <b>{action}: {format_amount(amount, self.user.currency)}</b>\n\n"
        )

        if description:
            message_text += f"📝 {description}\n\n"

        if suggested_category:
            message_text += f"💡 Suggested: <i>{suggested_category}</i>\n\n"

        if remaining_transactions:
            message_text += f"📊 {len(remaining_transactions) + 1} expenses need review\n\n"

        message_text += _("Select the correct category:")

        # Show category keyboard
        keyboard = get_category_keyboard(categories)
        await self.message.answer(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def _get_budget_info(
            self,
            category_id: int,
            new_amount: float
    ) -> Optional[str]:
        """Get budget status information"""
        try:
            budget_status = await self.budget_service.get_budget_status(
                self.user.user_id,
                category_id
            )

            if not budget_status:
                return None

            percentage = budget_status['percentage']
            spent = budget_status['spent']
            budget_amount = budget_status['budget'].amount

            if budget_status['is_exceeded']:
                return (
                    f"⚠️ <b>Budget exceeded!</b>\n"
                    f"Spent: {format_amount(spent, self.user.currency)} / "
                    f"{format_amount(budget_amount, self.user.currency)} "
                    f"({percentage}%)"
                )
            elif budget_status['is_warning']:
                return (
                    f"⚡ <b>Budget warning: {percentage}%</b>\n"
                    f"Spent: {format_amount(spent, self.user.currency)} / "
                    f"{format_amount(budget_amount, self.user.currency)}"
                )
            else:
                return (
                    f"✅ Budget: {format_amount(spent, self.user.currency)} / "
                    f"{format_amount(budget_amount, self.user.currency)} "
                    f"({percentage}%)"
                )
        except Exception as e:
            logger.error(f"Error getting budget info: {e}")
            return None

    @staticmethod
    def _get_confidence_indicator(confidence: float) -> str:
        """Get confidence indicator emoji"""
        if confidence < 0.6:
            return " 🤔"
        elif confidence < 0.75:
            return " 💭"
        elif confidence >= 0.9:
            return " ✨"
        return ""

    def _should_skip_input(self, text: str) -> bool:
        """
        Check if input should be skipped (invalid/garbage)
        Returns True if input looks like code, random characters, or spam
        """
        # Skip if contains code-like patterns
        code_patterns = [
            'self.',
            'def ',
            'class ',
            'import ',
            'from ',
            'async ',
            'await ',
            'return ',
            '() {',
            '[]',
            '{}',
            '=>',
            'function(',
            'const ',
            'let ',
            'var ',
        ]

        text_lower = text.lower()
        for pattern in code_patterns:
            if pattern in text_lower:
                return True

        # Skip if too many special characters (likely spam/garbage)
        special_chars = sum(1 for c in text if c in '()[]{}|\\<>@#$%^&*_=+`~')
        if special_chars > len(text) * 0.3:
            return True

        # Skip if looks like a URL
        if 'http://' in text_lower or 'https://' in text_lower or 'www.' in text_lower:
            return True

        # Skip if too long (likely spam)
        if len(text) > 200:
            return True

        return False

    async def _send_help_message(self, parse_result: Dict[str, Any]):
        """Send helpful message for unclear input"""
        await self.message.answer(
            _("🤔 <b>I couldn't understand that clearly.</b>\n\n"
              "<b>Try these formats:</b>\n"
              "• <code>50k taxi</code> - Quick expense\n"
              "• <code>lunch 25000</code> - Amount first or last\n"
              "• <code>bought groceries 120k</code> - With description\n"
              "• <code>received 5k from freelance</code> - For income\n\n"),
            parse_mode="HTML"
        )


# ==================== MESSAGE HANDLER ====================

@expense_router.message(
    F.text & ~F.text.startswith('/'),
    StateFilter(None)  # Only when not in any state
)
async def handle_natural_expense(
        message: Message,
        session: AsyncSession,
        state: FSMContext
):
    """
    Handle natural language expense/income input
    Entry point for all non-command text messages
    """
    text = message.text.strip()

    # Skip empty messages
    if not text:
        return

    # Skip casual chat
    if text.lower() in CASUAL_WORDS:
        return

    # Skip very short messages (likely typos or fragments)
    if len(text) < 2:
        return

    try:
        # Get or create user
        user, status = await User.get_or_create(
            user_id=message.from_user.id,
        )

        # Process with handler
        handler = ExpenseHandler(session, user, message, state)
        await handler.process_natural_input(text)

    except Exception as e:
        logger.exception(f"Critical error in natural expense handler: {e}")
        await message.answer(
            _("❌ <b>Unexpected error occurred</b>\n\nPlease try again or contact support if the issue persists."),
            parse_mode="HTML"
        )


# ==================== CATEGORY SELECTION CALLBACK ====================

@expense_router.callback_query(
    F.data.startswith("cat_"),
    ExpenseForm.waiting_for_category
)
async def category_selected(
        callback: CallbackQuery,
        session: AsyncSession,
        state: FSMContext
):
    """
    Handle category selection from inline keyboard

    CHANGE #9: Added support for processing remaining transactions in queue
    """
    try:
        # Parse category ID
        category_id = int(callback.data.split("_")[1])

        # Get state data
        data = await state.get_data()
        amount = data.get('amount')
        description = data.get('description', '')
        transaction_type = data.get('transaction_type', 'expense')
        remaining_transactions = data.get('remaining_transactions', [])


        # Validate data
        if not amount:
            await callback.answer(_("⚠️ Session expired. Please try again."), show_alert=True)
            await state.clear()
            return

        # Get user
        user, status = await User.get_or_create(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            first_name=callback.from_user.first_name
        )

        # Get category
        category: Category = await Category.filter_first(Category.id == category_id)

        if not category or category.user_id != user.user_id:
            await callback.answer(_("❌ Category not found"), show_alert=True)
            return

        # Create transaction
        transaction_service = TransactionService(session)
        transaction = await transaction_service.create_transaction(
            user_id=user.user_id,
            amount=amount,
            category_id=category.id,
            transaction_type=transaction_type,
            description=description,
            payment_method='cash' if transaction_type == 'expense' else 'bank'
        )

        # Build response
        emoji = "💸" if transaction_type == "expense" else "💰"
        sign = "-" if transaction_type == "expense" else "+"

        response = (
            f"✅ <b>{transaction_type.title()} {_('logged')}!</b>\n\n"
            f"{emoji} {sign}{format_amount(amount, user.currency)}\n"
            f"📁 {category.name}\n"
        )

        if description:
            response += f"📝 {description}\n"

        # Add budget info for expenses
        if transaction_type == 'expense':
            budget_service = BudgetService(session)
            budget_status = await budget_service.get_budget_status(
                user.user_id,
                category.id
            )

            if budget_status:
                percentage = budget_status['percentage']
                spent = budget_status['spent']
                budget_amount = budget_status['budget'].amount

                if budget_status['is_exceeded']:
                    response += (
                        f"\n⚠️ <b>Budget exceeded!</b>\n"
                        f"Spent: {format_amount(spent, user.currency)} / "
                        f"{format_amount(budget_amount, user.currency)}"
                    )
                elif budget_status['is_warning']:
                    response += (
                        f"\n⚡ <b>Budget warning: {percentage}%</b>\n"
                        f"Spent: {format_amount(spent, user.currency)} / "
                        f"{format_amount(budget_amount, user.currency)}"
                    )
                else:
                    response += (
                        f"\n✅ Budget: {percentage}%"
                    )

        await callback.message.edit_text(response, parse_mode="HTML")
        await callback.answer(_("✅ Saved!"))

        if remaining_transactions:
            next_txn = remaining_transactions[0]
            remaining = remaining_transactions[1:]

            # Create new handler instance for next transaction
            handler = ExpenseHandler(session, user, callback.message, state)

            await handler._request_category_selection(
                amount=next_txn['amount'],
                description=next_txn['description'],
                transaction_type='expense',
                suggested_category=next_txn.get('suggested_category'),
                remaining_transactions=remaining if remaining else None
            )
        else:
            # All done, clear state
            await state.clear()

    except ValueError:
        await callback.answer(_("❌ Invalid category"), show_alert=True)
    except Exception as e:
        logger.exception(f"Error in category selection: {e}")
        await callback.answer(
            "❌ Failed to save. Please try again.",
            show_alert=True
        )
        await state.clear()


# ==================== CANCEL HANDLER ====================

@expense_router.callback_query(
    F.data == "cancel",
    ExpenseForm.waiting_for_category
)
async def cancel_category_selection(callback: CallbackQuery, state: FSMContext):
    """Cancel category selection"""
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Cancelled</b>\n\n"
        "Transaction was not saved.",
        parse_mode="HTML"
    )
    await callback.answer()


# ==================== TODAY'S SUMMARY ====================

@expense_router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession):
    """Show today's expenses summary"""
    user = await User.get_or_create(user_id=message.from_user.id, username=message.from_user.username)
    user = user[0]

    transactions = await get_transactions_today(user_id=user.user_id)

    if not transactions:
        await message.answer(_("📊 No expenses recorded today."))
        return

    total = sum(t.amount for t in transactions)

    response = f"📊 <b>{_('Today\'s Expenses')}</b>\n\n"
    response += f"💸 {_('Total')}: {format_amount(total, user.currency)}\n"
    response += f"📝 {_('Transactions')}: {len(transactions)}\n\n"

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

    response += f"\n<b>{_('Recent transactions')}:</b>\n"
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
    user = await User.get(id_=message.from_user.id)

    transactions = await get_recent_transactions(session, user.user_id, limit=10)

    if not transactions:
        await message.answer(_("📊 No transactions yet. Start by logging your first expense!"))
        return

    response = f"📋 <b>{_('Recent Transactions')}</b>\n\n"

    for t in transactions:
        local_time = to_user_timezone(t.date, user.timezone)
        date_str = local_time.strftime("%d %b, %H:%M")
        type_emoji = "💸" if t.type == "expense" else "💰"

        response += f"{type_emoji} {t.category.icon_emoji} <b>{format_amount(t.amount, user.currency)}</b>\n"
        response += f"   {t.category.name}"
        if t.description:
            response += f" • {t.description}"
        response += f"\n   <i>{date_str}</i>\n\n"

    await message.answer(response, parse_mode="HTML")
