from typing import Dict, Any, Awaitable, Callable

from aiogram import Dispatcher, BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n

from bot.database.engine import db
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.maintenance import MaintenanceMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from .i18n import CustomI18nMiddleware
from .user import UserMiddleware
from ..services.user_service import user_service

i18n = I18n(path="bot/locales", default_locale="en", domain="messages")


class ServiceInjectionMiddleware(BaseMiddleware):
    """Injects services into data dict for all handlers and middlewares"""

    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Any:
        data["user_service"] = user_service

        return await handler(event, data)


def register_middleware(dp: Dispatcher):
    """Register middleware"""
    dp.update.outer_middleware(MaintenanceMiddleware())

    dp.update.middleware(ServiceInjectionMiddleware())

    dp.update.middleware(DatabaseMiddleware(db.get_sessionmaker))

    dp.message.middleware(UserMiddleware())
    dp.callback_query.middleware(UserMiddleware())

    dp.message.middleware(CustomI18nMiddleware(i18n))
    dp.callback_query.middleware(CustomI18nMiddleware(i18n))

    dp.message.outer_middleware(ThrottlingMiddleware())
