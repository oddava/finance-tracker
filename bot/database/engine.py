import ssl
from contextlib import asynccontextmanager
from typing import Optional, Any, Coroutine

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import DeclarativeBase

from bot.core.config import settings


ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ==================== Base Classes ====================

class Base(DeclarativeBase):
    """Base class for all database models with automatic table naming."""

    @declared_attr
    def __tablename__(self) -> str:
        """Generate table name from class name (e.g., UserProfile -> user_profiles)."""
        name = self.__name__[:1]
        for char in self.__name__[1:]:
            if char.isupper():
                name += '_'
            name += char
        name = name.lower()

        if name.endswith('y'):
            name = name[:-1] + 'ie'
        return name + 's'


# ==================== Database Manager ====================

class DatabaseManager:
    """Manages async database connection and session lifecycle."""

    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    def __getattr__(self, name):
        return getattr(self._session_factory, name)

    async def init(self, database_url: Optional[str] = None) -> None:
        """
        Initialize async database engine and session factory.

        Args:
            database_url: Database connection URL (defaults to settings.postgresl_url)
        """
        url = database_url or settings.async_postgres_url

        # Convert sync URL to async if needed
        if url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+asyncpg://')

        self._engine = create_async_engine(
            url,
            connect_args={"ssl": ssl_context},
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    @property
    def get_sessionmaker(self) -> async_sessionmaker[AsyncSession] | None:
        return self._session_factory

    async def create_all(self) -> None:
        """Create all database tables."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self) -> None:
        """Drop all database tables."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def session(self) -> AsyncSession:
        """
        Context manager for database sessions.

        Usage:
            async with db.session() as session:
                # Use session here
        """
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def close(self) -> None:
        """Close database engine and all connections."""
        if self._engine:
            await self._engine.dispose()

    @property
    def engine(self) -> AsyncEngine:
        """Get database engine."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine


# ==================== Global Database Instance ====================

db = DatabaseManager()

# ==================== Initialization Function ====================

async def init_database(database_url: Optional[str] = None, create_tables: bool = True) -> None:
    """
    Initialize the database system.

    Args:
        database_url: Optional database URL (defaults to settings)
        create_tables: Whether to create tables on init

    Usage in bot startup:
        async def on_startup(dispatcher):
            await init_database()
    """
    await db.init(database_url)
    if create_tables:
        await db.create_all()


async def close_database() -> None:
    """
    Close database connections.

    Usage in bot shutdown:
        async def on_shutdown(dispatcher):
            await close_database()
    """
    await db.close()
