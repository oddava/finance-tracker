from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Transaction


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_transaction(
            self,
            user_id: int,
            amount: float,
            category_id: int,
            transaction_type: str,
            description: str = "",
            payment_method: str = "cash"
    ) -> Transaction:
        """Create a new transaction"""
        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            category_id=category_id,
            type=transaction_type,
            description=description,
            payment_method=payment_method,
        )
        self.session.add(transaction)
        await self.session.commit()
        await self.session.refresh(transaction)
        return transaction