import asyncio
from datetime import datetime
from typing import Dict, Optional, List

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import Transaction, User


class BroadcastService:
    """Service for broadcasting messages to users"""

    def __init__(self, bot: Bot, session: AsyncSession):
        self.bot = bot
        self.session = session

    async def send_broadcast(
            self,
            text: str,
            parse_mode: str = "HTML",
            disable_notification: bool = False,
            exclude_user_ids: Optional[List[int]] = None
    ) -> Dict[str, int]:
        """
        Send broadcast message to all users

        Returns:
            Dict with success, failed, and blocked counts
        """
        result = await User.get_all()
        user_ids = [row.user_id for row in result]

        if exclude_user_ids:
            user_ids = [uid for uid in user_ids if uid not in exclude_user_ids]

        logger.info(f"Starting broadcast to {len(user_ids)} users")

        success = 0
        failed = 0
        blocked = 0

        # Send with rate limiting (20 messages per second for Telegram)
        for i, user_id in enumerate(user_ids, 1):
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification
                )
                success += 1

                # Log progress every 100 messages
                if i % 100 == 0:
                    logger.info(f"Broadcast progress: {i}/{len(user_ids)}")

                # Rate limiting: 20 messages per second
                if i % 20 == 0:
                    await asyncio.sleep(1)

            except TelegramForbiddenError:
                # User blocked the bot
                blocked += 1
                logger.debug(f"User {user_id} has blocked the bot")

            except TelegramBadRequest as e:
                # Invalid user or other error
                failed += 1
                logger.warning(f"Failed to send to {user_id}: {e}")

            except Exception as e:
                failed += 1
                logger.error(f"Unexpected error sending to {user_id}: {e}")

        result = {
            'success': success,
            'failed': failed,
            'blocked': blocked,
            'total': len(user_ids)
        }

        logger.info(f"Broadcast completed: {result}")
        return result

    async def send_to_active_users(
            self,
            text: str,
            days: int = 7,
            parse_mode: str = "HTML"
    ) -> Dict[str, int]:
        """
        Send message only to users active in last N days
        """
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)

        # Get active user IDs
        result = await self.session.execute(
            select(User.user_id)
            .join(Transaction, Transaction.user_id == User.user_id)
            .where(Transaction.created_at >= cutoff)
            .distinct()
        )
        user_ids = [row[0] for row in result]

        logger.info(f"Sending to {len(user_ids)} active users (last {days} days)")

        success = 0
        failed = 0
        blocked = 0

        for user_id in user_ids:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode=parse_mode
                )
                success += 1
                await asyncio.sleep(0.05)  # Rate limiting

            except (TelegramForbiddenError, TelegramBadRequest):
                blocked += 1
            except Exception:
                failed += 1

        return {
            'success': success,
            'failed': failed,
            'blocked': blocked,
            'total': len(user_ids)
        }