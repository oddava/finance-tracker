from datetime import datetime

from sqlalchemy import Integer, ForeignKey, Numeric, DateTime, String, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.crud import Model


class Budget(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)

    amount: Mapped[float] = mapped_column(Float)
    period: Mapped[str] = mapped_column(String(20), default="monthly")  # daily, weekly, monthly
    alert_threshold: Mapped[int] = mapped_column(Integer, default=80)  # Alert at 80%

    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="budgets")
    category: Mapped["Category"] = relationship(back_populates="budgets")

    def __repr__(self):
        return f"<Budget(id={self.id}, amount={self.amount}, period={self.period})>"