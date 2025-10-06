from datetime import datetime
from typing import List

from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from bot.database.crud import Model


class User(Model):
    class PersonalityType(str, enum.Enum):
        SAVER = "saver"
        BALANCED = "balanced"
        SPENDER = "spender"
        UNKNOWN = "unknown"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="en")
    currency: Mapped[str] = mapped_column(String(10), default="UZS")
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tashkent")
    personality_profile: Mapped[str] = mapped_column(
        String(20),
        default=PersonalityType.UNKNOWN.value
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    categories: Mapped[List["Category"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    budgets: Mapped[List["Budget"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )



    def __repr__(self):
        return f"<User(id={self.id}, user_id={self.telegram_id}, name={self.first_name})>"
