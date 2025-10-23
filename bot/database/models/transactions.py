from datetime import datetime

from sqlalchemy import Integer, ForeignKey, Numeric, String, Text, DateTime, JSON, func, Float
from sqlalchemy.orm import mapped_column, Mapped, relationship

from bot.database.crud import Model


class Transaction(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)

    type: Mapped[str] = mapped_column(String(20), index=True)  # 'expense' or 'income'
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="UZS")
    description: Mapped[str] = mapped_column(String(500), default="")

    date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    payment_method: Mapped[str] = mapped_column(String(50), default="cash")  # cash, card, online
    # Optional fields
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)  # ['food', 'lunch', 'restaurant']

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="transactions")
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(id={self.id}, type={self.type}, amount={self.amount})>"