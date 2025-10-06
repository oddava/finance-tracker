from datetime import datetime
from typing import List

from sqlalchemy import Integer, String, Boolean, ForeignKey, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.crud import Model


class Category(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    icon_emoji: Mapped[str] = mapped_column(String(10), default="💰")
    color: Mapped[str] = mapped_column(String(7), default="#95A5A6")  # Hex color
    type: Mapped[str] = mapped_column(String(20))  # 'expense' or 'income'
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="categories")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction",
        back_populates="category",
        cascade="all, delete-orphan"
    )
    budgets: Mapped[List["Budget"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Category(id={self.id}, name={self.name}, type={self.type})>"