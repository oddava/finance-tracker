# ==================== Model with Class Methods ====================
from typing import Any, Type, Optional, Sequence, TypeVar, List, Dict

from sqlalchemy import select, func, update as sqlalchemy_update, delete as sqlalchemy_delete
from sqlalchemy.orm import selectinload

from bot.database.engine import Base, db

T = TypeVar('T', bound='Model')

class Model(Base):
    """Base model class with convenient class methods for use in handlers."""

    __abstract__ = True

    # id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    def __str__(self):
        return f"{self.__class__.__name__}"

    @classmethod
    async def create(cls: Type[T], **kwargs) -> T:
        """
        Create a new record.

        Usage in handler:
            user = await User.create(telegram_id=message.from_user.id, name="John")
        """
        async with db.session() as session:
            obj = cls(**kwargs)
            session.add(obj)
            await session.flush()
            await session.refresh(obj)
            return obj

    @classmethod
    async def batch_create(cls: Type[T], list_of_kwargs: List[Dict]) -> List[T]:
        """
        Create multiple records at once.

        Example:
            users = await User.batch_create([
                {"telegram_id": 123, "name": "John"},
                {"telegram_id": 456, "name": "Alice"}
            ])
        """
        async with db.session() as session:
            objs = [cls(**kwargs) for kwargs in list_of_kwargs]
            session.add_all(objs)
            await session.flush()
            for obj in objs:
                await session.refresh(obj)
            return objs

    @classmethod
    async def get(cls: Type[T], id_: int, relationship: Optional[Any] = None):
        """
        Get a record by ID.

        Usage in handler:
            user = await User.get(user_id)
        """
        async with db.session() as session:
            query = select(cls).where(cls.user_id == id_)
            if relationship:
                query = query.options(selectinload(relationship))

            result = await session.execute(query)
            return result.scalar_one_or_none()

    @classmethod
    async def get_or_create(cls: Type[T], defaults: Optional[dict] = None, **kwargs) -> tuple[T, bool]:
        """
        Get existing record or create new one.

        Usage in handler:
            user, created = await User.get_or_create(
                telegram_id=message.from_user.id,
                defaults={'name': message.from_user.full_name}
            )

        Returns:
            Tuple of (instance, created) where created is True if new record was created
        """
        async with db.session() as session:
            query = select(cls).where(
                *[getattr(cls, key) == value for key, value in kwargs.items()]
            )
            result = await session.execute(query)
            obj = result.scalar_one_or_none()

            if obj:
                return obj, False

            create_kwargs = kwargs.copy()
            if defaults:
                create_kwargs.update(defaults)

            obj = cls(**create_kwargs)
            session.add(obj)
            await session.flush()
            await session.refresh(obj)
            return obj, True

    @classmethod
    async def update(cls, id_: int, **kwargs) -> None:
        """
        Update a record by ID.

        Usage in handler:
            await User.update(user_id, balance=100)
        """
        async with db.session() as session:
            query = (
                sqlalchemy_update(cls)
                .where(cls.user_id == id_)
                .values(**kwargs)
                .execution_options(synchronize_session="fetch")
            )
            await session.execute(query)

    @classmethod
    async def update_or_create(cls: Type[T], filter_by: dict, defaults: dict) -> tuple[T, bool]:
        """
        Update existing record or create new one.

        Usage in handler:
            user, created = await User.update_or_create(
                filter_by={'telegram_id': message.from_user.id},
                defaults={'name': message.from_user.full_name, 'balance': 0}
            )
        """
        async with db.session() as session:
            query = select(cls).where(
                *[getattr(cls, key) == value for key, value in filter_by.items()]
            )
            result = await session.execute(query)
            obj = result.scalar_one_or_none()

            if obj:
                for key, value in defaults.items():
                    setattr(obj, key, value)
                await session.flush()
                await session.refresh(obj)
                return obj, False

            create_kwargs = filter_by.copy()
            create_kwargs.update(defaults)
            obj = cls(**create_kwargs)
            session.add(obj)
            await session.flush()
            await session.refresh(obj)
            return obj, True

    @classmethod
    async def delete(cls, id_: int) -> None:
        """
        Delete a record by ID.

        Usage in handler:
            await User.delete(user_id)
        """
        async with db.session() as session:
            query = sqlalchemy_delete(cls).where(cls.id == id_)
            await session.execute(query)

    @classmethod
    async def count(cls, criteria: Optional[Any] = None) -> int:
        """
        Count records matching criteria.

        Usage in handler:
            total_users = await User.count()
            active_users = await User.count(User.is_active == True)
        """
        async with db.session() as session:
            query = select(func.count()).select_from(cls)
            if criteria is not None:
                query = query.where(criteria)

            result = await session.execute(query)
            return result.scalar_one()

    @classmethod
    async def filter_all(
            cls: Type[T],
            criteria: Any,
            relationship: Optional[Any] = None,
            columns: Optional[Sequence[Any]] = None,
            order_by: Optional[Any] = None,
            limit: Optional[int] = None
    ) -> Sequence[T]:
        """
        Get all records matching criteria.

        Usage in handler:
            users = await User.filter_all(User.is_active == True)
            users = await User.filter_all(User.balance > 100, order_by=User.balance.desc(), limit=10)
        """
        async with db.session() as session:
            if columns:
                query = select(*columns)
            else:
                query = select(cls)

            query = query.where(criteria)

            if relationship:
                query = query.options(selectinload(relationship))

            if order_by is not None:
                query = query.order_by(order_by)

            if limit:
                query = query.limit(limit)

            result = await session.execute(query)
            return result.scalars().all()

    @classmethod
    async def filter_first(
            cls: Type[T],
            criteria: Any,
            relationship: Optional[Any] = None,
            columns: Optional[Sequence[Any]] = None
    ) -> Optional[T]:
        """
        Get first record matching criteria.

        Usage in handler:
            user = await User.filter_first(User.telegram_id == message.from_user.id)
        """
        async with db.session() as session:
            if columns:
                query = select(*columns)
            else:
                query = select(cls)

            query = query.where(criteria)

            if relationship:
                query = query.options(selectinload(relationship))

            result = await session.execute(query)
            return result.scalars().first()

    @classmethod
    async def get_all(cls: Type[T], limit: Optional[int] = None) -> Sequence[T]:
        """
        Get all records ordered by ID descending.

        Usage in handler:
            all_users = await User.get_all()
            recent_users = await User.get_all(limit=10)
        """
        async with db.session() as session:
            query = select(cls).order_by(cls.id.desc())
            if limit:
                query = query.limit(limit)
            result = await session.execute(query)
            return result.scalars().all()

    @classmethod
    async def exists(cls, criteria: Any) -> bool:
        """
        Check if record exists.

        Usage in handler:
            exists = await User.exists(User.telegram_id == message.from_user.id)
        """
        return await cls.count(criteria) > 0

    async def save(self) -> None:
        """
        Save changes to this instance.

        Usage in handler:
            user = await User.get(user_id)
            user.balance += 10
            await user.save()
        """
        async with db.session() as session:
            session.add(self)
            await session.flush()
            await session.refresh(self)

    async def refresh(self) -> None:
        """
        Refresh this instance from database.

        Usage in handler:
            await user.refresh()
        """
        async with db.session() as session:
            await session.refresh(self)

