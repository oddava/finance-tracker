from dataclasses import dataclass

from cachetools import TTLCache
import asyncio

from loguru import logger

from bot.database import User
from bot.utils.helpers import create_default_categories


@dataclass
class CachedUser:
    user_id: int
    language_code: str
    exists: bool = True
    has_custom_categories: bool = False


class UserService:
    """Centralized user data management with caching"""

    def __init__(self, cache_size: int = 10000, cache_ttl: int = 3600):
        self._user_cache: TTLCache = TTLCache(maxsize=cache_size, ttl=cache_ttl)
        self._lock = asyncio.Lock()

        self._cache_hits = 0
        self._cache_misses = 0

    async def get_user_language(self, user_id: int, fallback: str = "en") -> str:
        """Get user language with caching"""
        cached = self._user_cache.get(user_id)
        if cached:
            self._cache_hits += 1
            return cached.language_code

        self._cache_misses += 1
        user = await User.get(user_id)
        language = getattr(user, "language_code", None) or fallback

        async with self._lock:
            self._user_cache[user_id] = CachedUser(
                user_id=user_id,
                language_code=language,
            )

        return language

    async def update_user_language(self, user_id: int, language: str) -> None:
        """Update language and invalidate cache"""
        logger.info(f"Updating user language for user {user_id}. Language: {language}")
        await User.update(id_=user_id, language_code=language)

        async with self._lock:
            self._user_cache[user_id] = CachedUser(
                user_id=user_id,
                language_code=language,
            )

    async def ensure_user_exists(self, user) -> None:
        """Create user if doesn't exist, cache their language"""
        user_id = user.id

        if user_id in self._user_cache:
            # logger.debug(f"User {user_id} already exists in cache")
            self._cache_hits += 1
            return

        # logger.debug(f"User {user_id} does not exist in cache, adding to cache and creating if needed")
        self._cache_misses += 1
        user_data = self._extract_telegram_data(user)
        user, created = await User.get_or_create(user_id=user_id, defaults=user_data)

        async with self._lock:
            self._user_cache[user_id] = CachedUser(
                user_id=user_id,
                language_code=user.language_code,
            )

        if created:
            # logger.info(f"User {user_id} has not been registered. Creating default categories.")
            self._user_cache[user_id].has_custom_categories = True
            await create_default_categories(user_id)

    def get_cache_stats(self):
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return f"Cache hits: {self._cache_hits}, misses: {self._cache_misses}, hit rate: {hit_rate:.1f}%"

    def _extract_telegram_data(self, telegram_user) -> dict:
        """Extract relevant data from Telegram user object"""
        return {
            "username": telegram_user.username,
            "first_name": telegram_user.first_name,
            "language_code": telegram_user.language_code or "en",
        }

user_service = UserService()
