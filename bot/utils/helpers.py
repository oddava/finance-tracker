from datetime import datetime, timezone
from typing import Optional, Sequence, List, Dict, Any, Coroutine

from aiogram.types import KeyboardButton
from asyncpg.pgproto.pgproto import timedelta
from slugify import slugify
from sqlalchemy import select, func, desc, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.operators import and_

from bot.database import Category, Transaction, Budget, User


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
    for category in default_categories:
        category["slug"] = slugify(category["name"])

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

    query = query.options(selectinload(Transaction.category))
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


# ==================== STATISTICS FUNCTIONS ====================

async def get_total_users(session=None) -> int:
    """Get total number of users"""
    user_count = await User.count()
    return user_count


async def get_active_users_today(session: AsyncSession) -> int:
    """Get users who created transactions today"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(func.count(func.distinct(Transaction.user_id)))
        .where(Transaction.created_at >= today)
    )
    return result.scalar() or 0


async def get_active_users_week(session: AsyncSession) -> int:
    """Get users who created transactions this week"""
    week_ago = datetime.now() - timedelta(days=7)

    result = await session.execute(
        select(func.count(func.distinct(Transaction.user_id)))
        .where(Transaction.created_at >= week_ago)
    )
    return result.scalar() or 0


async def get_new_users_today(session: AsyncSession) -> int:
    """Get users who joined today"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    result = await session.execute(
        select(func.count(User.user_id))
        .where(User.created_at >= today)
    )
    return result.scalar() or 0


async def get_transactions_count_today(session=None, user_id: int = None) -> int:
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    if user_id:
        return await Transaction.count((Transaction.created_at >= today_utc) & (Transaction.user_id == user_id))
    return await Transaction.count(Transaction.created_at >= today_utc)


async def get_transactions_today(user_id: int) -> Sequence[Transaction]:
    now_utc = datetime.now(timezone.utc)
    today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    transactions = await Transaction.filter_all(
        (Transaction.created_at >= today_utc) & (Transaction.user_id == user_id),
        relationship=Transaction.category
    )

    return transactions


async def get_transactions_count_total(session: AsyncSession) -> int:
    """Get total transactions ever"""
    result = await session.execute(
        select(func.count(Transaction.id))
    )
    return result.scalar() or 0


async def get_total_transaction_volume(session: AsyncSession) -> Dict:
    """Get total money tracked (expenses and income)"""
    result = await session.execute(
        select(
            Transaction.type,
            func.sum(Transaction.amount).label('total')
        )
        .group_by(Transaction.type)
    )

    volumes = {'expense': 0, 'income': 0}
    for row in result:
        volumes[row.type] = row.total or 0

    return volumes


async def get_top_users_by_transactions(
        session: AsyncSession,
        limit: int = 10
) -> List[Dict]:
    """Get most active users by transaction count"""
    result = await session.execute(
        select(
            User.user_id,
            User.username,
            User.first_name,
            func.count(Transaction.id).label('txn_count')
        )
        .join(Transaction, Transaction.user_id == User.user_id)
        .group_by(User.user_id, User.username, User.first_name)
        .order_by(desc('txn_count'))
        .limit(limit)
    )

    return [
        {
            'user_id': row.user_id,
            'username': row.username,
            'first_name': row.first_name,
            'count': row.txn_count
        }
        for row in result
    ]


async def get_popular_categories(
        session: AsyncSession,
        limit: int = 10
) -> List[Dict]:
    """Get most used categories"""
    result = await session.execute(
        select(
            Category.name,
            Category.icon_emoji,
            func.count(Transaction.id).label('usage_count')
        )
        .join(Transaction, Transaction.category_id == Category.id)
        .group_by(Category.id, Category.name, Category.icon_emoji)
        .order_by(desc('usage_count'))
        .limit(limit)
    )

    return [
        {
            'name': row.name,
            'icon': row.icon_emoji,
            'count': row.usage_count
        }
        for row in result
    ]


async def get_user_retention_stats(session: AsyncSession) -> Dict:
    """Calculate user retention (users who came back after first day)"""
    # Users created more than 1 day ago
    one_day_ago = datetime.now() - timedelta(days=1)

    result = await session.execute(
        select(func.count(User.user_id))
        .where(User.created_at < one_day_ago)
    )
    old_users = result.scalar() or 0

    if old_users == 0:
        return {'retention_rate': 0, 'retained_users': 0, 'total_old_users': 0}

    # Of those, how many have transactions after their first day?
    result = await session.execute(
        select(func.count(func.distinct(User.user_id)))
        .select_from(User)
        .join(Transaction, Transaction.user_id == User.user_id)
        .where(
            and_(
                User.created_at < one_day_ago,
                Transaction.created_at > User.created_at + timedelta(days=1)
            )
        )
    )
    retained = result.scalar() or 0

    return {
        'retention_rate': round((retained / old_users) * 100, 1),
        'retained_users': retained,
        'total_old_users': old_users
    }


async def get_database_size(session: AsyncSession) -> Optional[str]:
    """Get database size (PostgreSQL only)"""
    try:
        from sqlalchemy import text
        result = await session.execute(
            text("SELECT pg_size_pretty(pg_database_size(current_database()))")
        )
        return result.scalar()
    except Exception:
        return None
