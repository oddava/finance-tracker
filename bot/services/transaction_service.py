from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Transaction


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    async def create_transaction(
            user_id: int,
            amount: float,
            category_id: int,
            transaction_type: str,
            description: str = "",
            payment_method: str = "cash"
    ) -> Transaction:
        """Create a new transaction"""
        transaction = await Transaction.create(
            user_id=user_id,
            amount=amount,
            category_id=category_id,
            type=transaction_type,
            description=description,
            payment_method=payment_method,
        )
        return transaction