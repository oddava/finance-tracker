from aiogram.filters import Filter
from aiogram.types import Message

from bot.core.config import settings

ADMIN_IDS = settings.ADMIN_IDS

class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ADMIN_IDS