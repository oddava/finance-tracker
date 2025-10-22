import asyncio
from datetime import datetime, time
import time as def_time
from typing import Optional, Sequence, List, Dict, Any, Coroutine

from aiogram.types import KeyboardButton
from asyncpg.pgproto.pgproto import timedelta
from sqlalchemy import select, func, desc, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.operators import and_
from thefuzz import fuzz

from bot.database import Category, Transaction, Budget
from bot.keyboards.inline import get_category_keyboard


async def create_default_categories(session: AsyncSession, user_id: int):
    """Create default expense/income categories for new user"""
    default_categories = [
        # Expense categories
        {"name": "Food", "icon_emoji": "🍔", "type": "expense", "color": "#FF6B6B"},
        {"name": "Transport", "icon_emoji": "🚗", "type": "expense", "color": "#4ECDC4"},
        {"name": "Groceries", "icon_emoji": "🛒", "type": "expense", "color": "#45B7D1"},
        {"name": "Entertainment", "icon_emoji": "🎮", "type": "expense", "color": "#FFA07A"},
        {"name": "Shopping", "icon_emoji": "🛍️", "type": "expense", "color": "#98D8C8"},
        {"name": "Bills & Utilities", "icon_emoji": "💡", "type": "expense", "color": "#F7DC6F"},
        {"name": "Healthcare", "icon_emoji": "🏥", "type": "expense", "color": "#BB8FCE"},
        {"name": "Education", "icon_emoji": "📚", "type": "expense", "color": "#85C1E2"},
        {"name": "Other", "icon_emoji": "💸", "type": "expense", "color": "#BDC3C7"},

        # Income categories
        {"name": "Salary", "icon_emoji": "💰", "type": "income", "color": "#2ECC71"},
        {"name": "Freelance", "icon_emoji": "💼", "type": "income", "color": "#27AE60"},
        {"name": "Investment", "icon_emoji": "📈", "type": "income", "color": "#16A085"},
        {"name": "Gift", "icon_emoji": "🎁", "type": "income", "color": "#52BE80"},
        {"name": "Other Income", "icon_emoji": "💵", "type": "income", "color": "#58D68D"},
    ]

    for cat_data in default_categories:
        category = Category(user_id=user_id, is_default=True, **cat_data)
        session.add(category)

    await session.commit()


async def get_user_categories(
        user_id: int,
        category_type: Optional[str] = None
) -> List[Category]:
    """Get all categories for a user (default + custom)"""

    if category_type:
        categories = await Category.filter_all(
            criteria=((Category.user_id == user_id) & (Category.type == category_type))
        )
    else:
        categories = await Category.filter_all(Category.user_id == user_id)

    categories = list(categories)
    return categories



async def get_category_by_name(
        user_id: int,
        name: str
) -> Optional[Category]:
    """Find category by name (case-insensitive)"""
    res = await Category.filter_first((Category.user_id == user_id) & (func.lower(Category.name) == name.lower()))
    return res


async def create_custom_category(
        user_id: int,
        name: str,
        icon_emoji: str,
        category_type: str,
        color: str = "#95A5A6"
) -> Category:
    """Create a custom category for user"""
    category = {
        "user_id": user_id,
        "name": name,
        "icon_emoji": icon_emoji,
        "type": category_type,
        "color": color,
        "is_default": True,
    }

    return await Category.create(**category)


async def create_transaction(
        user_id: int,
        amount: float,
        category_id: int,
        transaction_type: str,  # 'expense' or 'income'
        description: Optional[str] = None,
        date: Optional[datetime] = None,
        payment_method: str = "cash",
        tags: Optional[List[str]] = None,
        photo_url: Optional[str] = None
) -> Transaction:
    """Create a new transaction"""
    transaction = {
        "user_id": user_id,
        "type": transaction_type,
        "amount": amount,
        "category_id": category_id,
        "description": description or "",
        "date": date or datetime.now(),
        "payment_method": payment_method,
        "tags": tags or [],
        "photo_url": photo_url
    }
    return await Transaction.create(**transaction)


async def get_recent_transactions(
        session: AsyncSession,
        user_id: int,
        limit: int = 10,
        days: Optional[int] = None
) -> Sequence[Transaction]:
    """Get recent transactions for a user"""
    query = select(Transaction).where(Transaction.user_id == user_id)

    if days:
        start_date = datetime.now() - timedelta(days=days)
        query = query.where(Transaction.date >= start_date)

    query = query.options(selectinload(Transaction.category))
    query = query.order_by(desc(Transaction.date), desc(Transaction.created_at))
    query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


async def get_transactions_by_period(
        session: AsyncSession,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        transaction_type: Optional[str] = None
) -> Sequence[Transaction]:
    """Get transactions within a date range"""
    query = select(Transaction).where(
        (Transaction.user_id == user_id) &
        (Transaction.date >= start_date) &
        (Transaction.date <= end_date)
    )

    if transaction_type:
        query = query.where(Transaction.type == transaction_type)

    query = query.options(selectinload(Transaction.category_id))
    query = query.order_by(desc(Transaction.date))

    result = await session.execute(query)
    return result.scalars().all()


async def get_monthly_summary(
        session: AsyncSession,
        user_id: int,
        year: int,
        month: int
) -> Dict:
    """Get monthly financial summary"""
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    # Total expenses
    expense_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            (Transaction.user_id == user_id) &
            (Transaction.type == "expense") &
            (Transaction.date >= start_date) &
            (Transaction.date < end_date)
        )
    )
    total_expenses = expense_result.scalar() or 0.0

    # Total income
    income_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            (Transaction.user_id == user_id) &
            (Transaction.type == "income") &
            (Transaction.date >= start_date) &
            (Transaction.date < end_date)
        )
    )
    total_income = income_result.scalar() or 0.0

    # Category breakdown
    category_result = await session.execute(
        select(
            Category.name,
            Category.icon_emoji,
            func.sum(Transaction.amount).label('total')
        )
        .join(Transaction.category)
        .where(
            (Transaction.user_id == user_id) &
            (Transaction.type == "expense") &
            (Transaction.date >= start_date) &
            (Transaction.date < end_date)
        )
        .group_by(Category.name, Category.icon_emoji)
        .order_by(desc('total'))
    )

    categories = [
        {
            "name": row.name,
            "emoji": row.icon_emoji,
            "amount": float(row.total)
        }
        for row in category_result.all()
    ]

    # Transaction count
    count_result = await session.execute(
        select(func.count(Transaction.id)).where(
            (Transaction.user_id == user_id) &
            (Transaction.date >= start_date) &
            (Transaction.date < end_date)
        )
    )
    transaction_count = count_result.scalar()

    return {
        "total_expenses": float(total_expenses),
        "total_income": float(total_income),
        "balance": float(total_income - total_expenses),
        "categories": categories,
        "transaction_count": transaction_count,
        "period": f"{year}-{month:02d}"
    }


async def update_transaction(
        session: AsyncSession,
        transaction_id: int,
        user_id: int,
        **kwargs
) -> Optional[Transaction]:
    """Update an existing transaction"""
    result = await session.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            )
        )
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        return None

    for key, value in kwargs.items():
        if hasattr(transaction, key):
            setattr(transaction, key, value)

    await session.commit()
    await session.refresh(transaction)
    return transaction


async def delete_transaction(
        session: AsyncSession,
        transaction_id: int,
        user_id: int
) -> bool:
    """Delete a transaction"""
    result = await session.execute(
        select(Transaction).where(
            and_(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id
            )
        )
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        return False

    await session.delete(transaction)
    await session.commit()
    return True


# ==================== BUDGET OPERATIONS ====================

async def create_budget(
        session: AsyncSession,
        user_id: int,
        category_id: int,
        amount: float,
        period: str = "monthly",
        alert_threshold: int = 80
) -> Budget:
    """Create a budget for a category"""
    budget = {
        "user_id": user_id,
        "category_id": category_id,
        "amount": amount,
        "period": period,
        "alert_threshold": alert_threshold,
        "start_date": datetime.now()
    }
    return await Budget.create(**budget)


async def get_budget_status(
        session: AsyncSession,
        user_id: int,
        category_id: int
) -> Optional[Dict]:
    """Get budget status with current spending"""
    result = await session.execute(
        select(Budget)
        .where(
            and_(
                Budget.user_id == user_id,
                Budget.category_id == category_id
            )
        )
        .options(selectinload(Budget.category))
    )
    budget = result.scalar_one_or_none()

    if not budget:
        return None

    # Calculate spent amount for current period
    now = datetime.now()
    if budget.period == "monthly":
        start_date = datetime(now.year, now.month, 1)
    elif budget.period == "weekly":
        start_date = now - timedelta(days=now.weekday())
    else:  # daily
        start_date = datetime(now.year, now.month, now.day)

    spent_result = await session.execute(
        select(func.sum(Transaction.amount)).where(
            (Transaction.user_id == user_id) &
            (Transaction.category_id == category_id) &
            (Transaction.type == "expense") &
            Transaction.date >= start_date
        )
    )
    spent = spent_result.scalar() or 0.0

    percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0

    return {
        "budget": budget,
        "spent": float(spent),
        "remaining": float(budget.amount - spent),
        "percentage": round(percentage, 1),
        "is_exceeded": spent > budget.amount,
        "is_warning": percentage >= budget.alert_threshold
    }


async def get_all_budgets_status(
        session: AsyncSession,
        user_id: int
) -> List[Dict]:
    """Get status for all user budgets"""
    result = await session.execute(
        select(Budget)
        .where(Budget.user_id == user_id)
        .options(selectinload(Budget.category))
    )
    budgets = result.scalars().all()

    statuses = []
    for budget in budgets:
        status = await get_budget_status(session, user_id, budget.category_id)
        if status:
            statuses.append(status)

    return statuses


# ==================== ANALYTICS ====================

async def get_spending_patterns(
        session: AsyncSession,
        user_id: int,
        days: int = 30
) -> Dict:
    """Analyze spending patterns"""
    start_date = datetime.now() - timedelta(days=days)

    # Day of week pattern
    dow_result = await session.execute(
        select(
            extract('dow', Transaction.date).label('day_of_week'),
            func.avg(Transaction.amount).label('avg_amount'),
            func.count(Transaction.id).label('count')
        )
        .where(
            (Transaction.user_id == user_id) &
            (Transaction.type == "expense") &
            Transaction.date >= start_date
        )
        .group_by('day_of_week')
        .order_by('day_of_week')
    )

    day_patterns = {
        int(row.day_of_week): {
            "avg_amount": float(row.avg_amount),
            "count": row.count
        }
        for row in dow_result.all()
    }

    # Top categories
    top_cats_result = await session.execute(
        select(
            Category.name,
            func.sum(Transaction.amount).label('total')
        )
        .join(Transaction.category)
        .where(
            (Transaction.user_id == user_id) &
            (Transaction.type == "expense") &
            Transaction.date >= start_date
        )
        .group_by(Category.name)
        .order_by(desc('total'))
        .limit(5)
    )

    top_categories = [
        {"name": row.name, "total": float(row.total)}
        for row in top_cats_result.all()
    ]

    return {
        "day_patterns": day_patterns,
        "top_categories": top_categories,
        "period_days": days
    }


async def show_typing_periodically(bot, chat_id, interval=3.0, max_seconds=10):
    """Show typing indicator periodically until cancelled or max time reached"""
    start_time = def_time.time()
    try:
        while def_time.time() - start_time < max_seconds:
            await bot.send_chat_action(chat_id, "typing")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        # Expected cancellation when response is ready
        pass


async def get_category_by_name_fuzzy(session, user_id, category_name, category_type):
    """Get category by name with fuzzy matching for better UX"""
    if not category_name:
        return None

    # Get all user categories of specified type
    categories = await get_user_categories(session, user_id, category_type=category_type)

    # Exact match first
    for cat in categories:
        if cat.name.lower() == category_name.lower():
            return cat

    # Then try fuzzy matching
    best_match = None
    best_score = 0

    for cat in categories:
        # Calculate fuzzy match score
        score = fuzz.ratio(cat.name.lower(), category_name.lower())

        # Check if this is a substring match
        if cat.name.lower() in category_name.lower() or category_name.lower() in cat.name.lower():
            score += 15  # Boost score for substring matches

        if score > best_score and score >= 70:  # 70% similarity threshold
            best_score = score
            best_match = cat

    return best_match


async def get_smart_category_keyboard(session, user_id, categories):
    """Create a keyboard with categories ordered by frequency of use"""
    # Get usage statistics for categories
    category_usage = await get_category_usage_stats(session, user_id)

    # Sort categories by usage frequency
    sorted_categories = sorted(
        categories,
        key=lambda cat: category_usage.get(cat.id, 0),
        reverse=True
    )

    # Create keyboard with most used categories first
    return get_category_keyboard(sorted_categories)


def add_new_category_button(keyboard, category_name):
    """Add a button to create a new category with the suggested name"""
    # Add a new row with the "Create new category" button
    new_button = KeyboardButton(text=f"➕ Create '{category_name}'")

    # Check if the keyboard already has buttons
    if keyboard.keyboard:
        keyboard.keyboard.append([new_button])
    else:
        keyboard.keyboard = [[new_button]]

    return keyboard


def add_default_button(keyboard, button_text):
    """Add a default/quick action button to the keyboard"""
    new_button = KeyboardButton(text=f"✅ {button_text}")

    # Add to the first row for prominence
    if keyboard.keyboard:
        if len(keyboard.keyboard[0]) < 2:  # If first row has space
            keyboard.keyboard[0].append(new_button)
        else:
            keyboard.keyboard.insert(0, [new_button])  # New first row
    else:
        keyboard.keyboard = [[new_button]]

    return keyboard


async def create_category(
        session: AsyncSession,
        user_id: int,
        name: str,
        type: str = "expense",
        icon_emoji: str = "📂",
        color: str = "#808080",
        is_default: bool = False
) -> Category:
    """
    Create a new category or return existing if it already exists for the user.

    Args:
        session: SQLAlchemy async session
        user_id: Owner of the category (None for default categories)
        name: Category name (e.g. "Food", "Transport")
        type: "expense" or "income"
        icon_emoji: Emoji icon
        color: HEX color string
        is_default: Whether this category is a system default

    Returns:
        Category object
    """
    # Check if category already exists for this user (case-insensitive)
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.name.ilike(name),
        Category.type == type
    )
    result = await session.execute(stmt)
    existing = result.scalars().first()

    if existing:
        return existing

    category = Category(
        user_id=user_id,
        name=name.capitalize(),
        type=type,
        icon_emoji=icon_emoji,
        color=color,
        is_default=is_default
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def maybe_show_streak(message, user, session):
    """Show streak or achievement message if applicable"""
    # This is a placeholder for streak/gamification features
    # You could implement daily streak tracking, achievements for consistent logging, etc.

    # Example: Count transactions today
    today_count = await count_transactions_today(session, user.user_id)

    # First transaction of the day
    if today_count == 1:
        await message.answer(
            "🔥 You've logged your first transaction today! Keep it up!",
            parse_mode="HTML"
        )
    # Achievement for 5 transactions in a day
    elif today_count == 5:
        await message.answer(
            "🏆 <b>Achievement unlocked:</b> Meticulous Tracker\n"
            "You've logged 5 transactions today. Great job staying on top of your finances!",
            parse_mode="HTML"
        )


async def count_transactions_today(session, user_id):
    """Count how many transactions the user has made today"""
    today = datetime.now().date()
    today_start = datetime.combine(today, time.min)
    today_end = datetime.combine(today, time.max)

    result = await session.execute(
        select(func.count(Transaction.id))
        .where(
            (Transaction.user_id == user_id) &
            (Transaction.created_at >= today_start) &
            Transaction.created_at <= today_end
        )
    )

    return result.scalar_one()


async def get_category_usage_stats(session, user_id, days=30):
    """Get category usage statistics for smart ordering"""
    # Get date for filtering recent transactions
    recent_date = datetime.now() - timedelta(days=days)

    # Query to count transactions by category
    result = await session.execute(
        select(Transaction.category_id, func.count(Transaction.id).label('count'))
        .where(
            Transaction.user_id == user_id,
            Transaction.created_at >= recent_date
        )
        .group_by(Transaction.category_id)
    )

    # Convert to dictionary {category_id: count}
    return {row[0]: row[1] for row in result.all()}
