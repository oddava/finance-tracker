from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.crud import Model


class BotSetting(Model):
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, default=None)