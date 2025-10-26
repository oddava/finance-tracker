from aiogram.utils.i18n import I18n
from aiogram.utils.i18n.middleware import I18nMiddleware
from aiogram.types import TelegramObject
from typing import Any, Dict, Optional

from bot.utils.perf import measure


class CustomI18nMiddleware(I18nMiddleware):
    def __init__(self, i18n: I18n, i18n_key: Optional[str] = "i18n", middleware_key: str = "i18n_middleware") -> None:
        super().__init__(i18n, i18n_key, middleware_key)
        self.default_locale = i18n.default_locale

    async def get_locale(self, event: TelegramObject, data: Dict[str, Any]) -> str:
        async with measure("get_locale"):
            user = data.get("event_from_user")
            if not user:
                return self.default_locale or "en"

            user_service = data["user_service"]
            telegram_fallback = user.language_code or "en"

            return await user_service.get_user_language(
                user_id=user.id,
                fallback=telegram_fallback
            )
