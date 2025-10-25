from aiogram import Dispatcher
from aiogram.utils.i18n import I18n

from bot.database.engine import db
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.maintenance import MaintenanceMiddleware
from bot.middlewares.throttling import ThrottlingMiddleware
from .i18n import CustomI18nMiddleware

i18n = I18n(path="bot/locales", default_locale="en", domain="messages")


def register_middleware(dp: Dispatcher):
    """Register middleware"""
    dp.message.middleware(DatabaseMiddleware(db.get_sessionmaker))
    dp.message.middleware(CustomI18nMiddleware(i18n))
    dp.message.outer_middleware(ThrottlingMiddleware())

    dp.callback_query.middleware(CustomI18nMiddleware(i18n))

    dp.update.outer_middleware(MaintenanceMiddleware())
    dp.update.middleware(DatabaseMiddleware(db.get_sessionmaker))
