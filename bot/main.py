import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.database import init_database, close_database
from bot.database.engine import db
from bot.handlers import router
from bot.middlewares.database import DatabaseMiddleware

TOKEN = settings.BOT_TOKEN

dp = Dispatcher()


async def on_startup():
    await init_database()
    dp.message.middleware(DatabaseMiddleware(db.get_sessionmaker))
    dp.update.middleware(DatabaseMiddleware(db.get_sessionmaker))
    print("Database initialized")

async def on_shutdown():
    await close_database()
    print("Database closed")



async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())