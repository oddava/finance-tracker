from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import Category


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_categories(
            self,
            user_id: int,
            category_type: Optional[str] = None
    ) -> Sequence[Category]:
        """Get all categories for a user"""
        query = select(Category).where(Category.user_id == user_id)
        if category_type:
            query = query.where(Category.type == category_type)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_category_by_name(
            self,
            user_id: int,
            name: str,
            category_type: Optional[str] = None
    ) -> Optional[Category]:
        """Find category by name (case-insensitive)"""
        query = select(Category).where(
            Category.user_id == user_id,
            Category.name.ilike(name)
        )
        if category_type:
            query = query.where(Category.type == category_type)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
