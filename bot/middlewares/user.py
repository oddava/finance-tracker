from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from loguru import logger

from bot.utils.perf import measure


class UserMiddleware(BaseMiddleware):
    """Ensures user exists in DB before processing"""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        async with measure("user_middleware"):
            user = data.get("event_from_user")
            if user:
                user_service = data["user_service"]
                await user_service.ensure_user_exists(
                    user=user,
                )

            return await handler(event, data)
