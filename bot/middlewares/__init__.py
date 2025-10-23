from aiogram import Dispatcher

from bot.database.engine import db
from bot.middlewares.database import DatabaseMiddleware
from bot.middlewares.maintenance import MaintenanceMiddleware


def register_middleware(dp: Dispatcher):
    """Register middleware"""
    dp.update.outer_middleware(MaintenanceMiddleware())
    dp.message.middleware(DatabaseMiddleware(db.get_sessionmaker))
    dp.update.middleware(DatabaseMiddleware(db.get_sessionmaker))