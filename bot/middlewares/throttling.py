from aiogram import BaseMiddleware
from cachetools import TTLCache

from bot.core.config import settings


class ThrottlingMiddleware(BaseMiddleware):
    """Rate limit users to prevent spam/abuse"""

    def __init__(self, rate_limit: int = 30):
        self.cache = TTLCache(maxsize=10000, ttl=60)
        self.rate_limit = rate_limit
        self.warned_users = TTLCache(maxsize=1000, ttl=300)

    async def __call__(self, handler, event, data):
        if not hasattr(event, 'from_user'):
            return await handler(event, data)

        user_id = event.from_user.id

        if user_id in settings.ADMIN_IDS:
            return await handler(event, data)

        # Check rate limit
        count = self.cache.get(user_id, 0)

        if count >= self.rate_limit:
            # Only warn once per cooldown period
            if user_id not in self.warned_users:
                self.warned_users[user_id] = True
                bot = data.get('bot')
                if bot and hasattr(event, 'chat'):
                    await bot.send_message(
                        event.chat.id,
                        "⚠️ <b>Slow down!</b>\n\n"
                        "You're sending messages too quickly. Please wait a moment.",
                        parse_mode="HTML"
                    )
            return None

        self.cache[user_id] = count + 1
        return await handler(event, data)
