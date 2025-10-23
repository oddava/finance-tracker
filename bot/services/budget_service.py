from typing import Optional, Dict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Budget, Transaction


class BudgetService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_budget_status(
            self,
            user_id: int,
            category_id: int
    ) -> Optional[Dict]:
        """Get budget status for a category"""
        # Get budget
        result = await self.session.execute(
            select(Budget).where(
                Budget.user_id == user_id,
                Budget.category_id == category_id
            )
        )
        budget = result.scalar_one_or_none()

        if not budget:
            return None

        # Calculate spent amount (this period)
        # Adjust the query based on your budget period logic
        spent = await self._calculate_spent(user_id, category_id)

        percentage = (spent / budget.amount * 100) if budget.amount > 0 else 0

        return {
            'budget': budget,
            'spent': spent,
            'percentage': round(percentage, 1),
            'is_exceeded': spent > budget.amount,
            'is_warning': budget.amount * 0.8 < spent <= budget.amount
        }

    async def _calculate_spent(self, user_id: int, category_id: int) -> float:
        """Calculate total spent in current period"""
        # Implement based on your budget period logic
        # This is a simple example
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user_id,
                Transaction.category_id == category_id,
                Transaction.type == 'expense'
            )
        )
        return result.scalar() or 0.0