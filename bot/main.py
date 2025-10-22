import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from aiogram.filters import Command

from bot.config import settings
from bot.database import init_database, close_database
from bot.database.engine import db
from bot.handlers import router
from bot.middlewares.database import DatabaseMiddleware

TOKEN = settings.BOT_TOKEN
WEBHOOK_URL = settings.WEBHOOK_URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_PORT = settings.WEBHOOK_PORT

# Global bot instance
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


async def on_startup():
    """Initialize database and webhook"""
    await init_database()

    # Add middleware AFTER database init
    dp.message.middleware(DatabaseMiddleware(db.get_sessionmaker))
    dp.update.middleware(DatabaseMiddleware(db.get_sessionmaker))

    # Include routers
    dp.include_router(router)

    # Set webhook
    await bot.set_webhook(
        url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    print("✅ Database initialized and webhook set!")


async def on_shutdown():
    """Clean shutdown"""
    await close_database()
    await bot.session.close()
    print("✅ Database closed and bot session closed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await on_startup()
    yield
    await on_shutdown()


# Create FastAPI app
app = FastAPI(lifespan=lifespan)


@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    """Receive and process Telegram updates"""
    json_data = await request.json()
    update = Update(**json_data)
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok", "webhook_url": f"{WEBHOOK_URL}{WEBHOOK_PATH}"}


@app.get("/set-webhook")
async def set_webhook_manual():
    """Manual webhook setup endpoint for debugging"""
    await bot.set_webhook(
        url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )
    return {"status": "webhook_set"}


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

    uvicorn.run(
        "bot.main:app",
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        reload=True,
        log_level="info"
    )