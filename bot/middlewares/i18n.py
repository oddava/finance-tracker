from bot.database import User

from aiogram.utils.i18n.middleware import I18nMiddleware
from aiogram.types import TelegramObject
from typing import Any, Dict


class CustomI18nMiddleware(I18nMiddleware):
    async def get_locale(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        user = await User.get(data.get("event_from_user").id)
        user_language = None

        if user is not None:
            user_language = user.language

        return user_language or data.get("event_from_user").language_code or "en"
