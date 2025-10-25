import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
import uvloop
from fastapi import FastAPI, Request, Header, HTTPException
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Update
from loguru import logger
from sqlalchemy import text

from bot.core.config import settings
from bot.database import init_database, close_database, BotSetting
from bot.database.engine import db
from bot.handlers import router
from bot.middlewares import register_middleware
from bot.utils.helpers import get_transactions_count_today, get_total_users
from bot.utils.logging_config import setup_sentry

TOKEN = settings.BOT_TOKEN
WEBHOOK_URL = settings.WEBHOOK_URL
WEBHOOK_PATH = "/webhook"
WEBHOOK_PORT = settings.WEBHOOK_PORT
WEBHOOK_SECRET = settings.WEBHOOK_SECRET

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


async def setup_bot():
    """Common bot setup for both modes"""
    await init_database()
    register_middleware(dp)
    dp.include_router(router)

    try:
        maintenance, _ = await BotSetting.get_or_create(key="maintenance_mode")
        if maintenance is not None:
            maintenance_status = maintenance.value.lower() == "true"
            settings.MAINTENANCE_MODE = maintenance_status
    except AttributeError:
        pass

    bot_info = await bot.get_me()
    logger.info(f"Name     - {bot_info.full_name}")
    logger.info(f"Username - @{bot_info.username}")
    logger.info(f"ID       - {bot_info.id}")

    states = {
        True: "Enabled",
        False: "Disabled",
        None: "Unknown (Not a bot)",
    }

    logger.info(f"Groups Mode  - {states[bot_info.can_join_groups]}")
    logger.info(f"Privacy Mode - {states[not bot_info.can_read_all_group_messages]}")
    logger.info(f"Inline Mode  - {states[bot_info.supports_inline_queries]}")


async def on_startup_webhook():
    """Startup for webhook mode"""
    logger.info("Starting bot in WEBHOOK mode...")
    await setup_bot()
    setup_sentry()

    await bot.set_webhook(
        url=f"{WEBHOOK_URL}{WEBHOOK_PATH}",
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
        secret_token=WEBHOOK_SECRET,
    )
    logger.success("✅ Bot started in WEBHOOK mode!")


async def on_startup_polling():
    """Startup for polling mode"""
    logger.info("Starting bot in POLLING mode...")
    await setup_bot()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.success("✅ Bot started in POLLING mode!")


async def on_shutdown():
    """Clean shutdown"""
    logger.info("Shutting down bot...")
    await close_database()
    await bot.delete_webhook(drop_pending_updates=False)

    await bot.session.close()
    logger.success("✅ Bot stopped successfully")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan for webhook mode only"""
    await on_startup_webhook()
    yield
    await on_shutdown()
app = FastAPI(lifespan=lifespan)


@app.post(WEBHOOK_PATH)
async def webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str = Header(None)
):
    """Receive and process Telegram updates"""
    # Validate secret token
    if x_telegram_bot_api_secret_token != WEBHOOK_SECRET:
        logger.warning("⚠️ Invalid webhook secret token received")
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        json_data = await request.json()
        update = Update(**json_data)
        await dp.feed_update(bot, update)
    except Exception as e:
        logger.exception(f"❌ Error processing update: {e}")

    return {"ok": True}

bot_start_time = datetime.now()
@app.get("/health")
@app.head("/health")
async def health_check():
    """Health check for monitoring"""
    uptime = (datetime.now() - bot_start_time).total_seconds()

    try:
        async with db.session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        print(f"Health check DB error: {e}")
        db_status = "unhealthy"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "uptime_seconds": uptime,
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint"""
    # Add your metrics here
    return {
        "total_users": await get_total_users(),
        "transactions_today": await get_transactions_count_today(),
    }

async def main():
    """Main entry point for polling mode"""
    dp.startup.register(on_startup_polling)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    if settings.DEBUG:
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    logger.add(
        "logs/bot_{time:YYYY-MM-DD}.log",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
        rotation="100 MB",
        retention="30 days",
        compression="zip",
        backtrace=True,
        diagnose=True if settings.DEBUG else False,
    )

    if settings.USE_WEBHOOK:
        logger.info("🚀 Starting in WEBHOOK mode...")
        uvicorn.run(
            "bot.__main__:app",
            host="0.0.0.0",
            port=WEBHOOK_PORT,
            reload=True,
            log_level="info",
        )
    else:
        logger.info("🚀 Starting in POLLING mode...")
        uvloop.run(main())