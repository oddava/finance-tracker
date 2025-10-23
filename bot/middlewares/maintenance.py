from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from loguru import logger

from bot.core.config import settings

ADMIN_IDS = settings.ADMIN_IDS


class MaintenanceMiddleware(BaseMiddleware):
    """Block all interactions during maintenance mode"""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any],
    ) -> Any:
        maintenance_mode = settings.MAINTENANCE_MODE
        logger.info(f"Maintenance mode: {maintenance_mode}")
        if not maintenance_mode:
            return await handler(event, data)
        # Log maintenance mode access attempt
        user = None
        if isinstance(event, Message):
            user = event.from_user
            chat_id = event.chat.id
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            chat_id = event.message.chat.id if event.message else event.from_user.id
        else:
            try:
                if isinstance(event, Update):
                    if event.message:
                        user = event.message.from_user
                        chat_id = event.message.chat.id
                    elif event.callback_query:
                        cq = event.callback_query
                        user = cq.from_user
                        chat_id = cq.message.chat.id if cq.message and cq.message.chat else user.id
                    else:
                        # logger.info(f"MaintenanceMiddleware: Update event with unsupported inner type: {event}")
                        return await handler(event, data)
                else:
                    if hasattr(event, "message") and getattr(event, "message"):
                        msg = getattr(event, "message")
                        user = getattr(msg, "from_user", None)
                        chat_id = getattr(msg, "chat", None) and getattr(msg.chat, "id", None)
                    else:
                        # logger.info(f"MaintenanceMiddleware: Unknown event shape: {type(event)}")
                        return await handler(event, data)
            except Exception as exc:
                logger.exception(f"Error while normalizing event in MaintenanceMiddleware: {exc}")
                return await handler(event, data)

        # Allow admins to bypass maintenance mode
        if user.id in ADMIN_IDS:
            logger.info(f"✅ Admin {user.id} bypassed maintenance mode")
            return await handler(event, data)
        logger.warning(
            f"⚠️ Maintenance mode: Blocked request from user {user.id} "
            f"(@{user.username or 'no_username'})"
        )

        # Send maintenance message
        bot = data.get("bot")
        if bot:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=settings.MAINTENANCE_MESSAGE,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Failed to send maintenance message: {e}")

        # Don't call the handler - stop processing
        return None
