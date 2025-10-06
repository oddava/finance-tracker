from datetime import datetime

from sqlalchemy import Integer, ForeignKey, String, Numeric, DateTime, Float, Boolean, func
from sqlalchemy.orm import mapped_column, Mapped, relationship

from bot.database.crud import Model


class Subscription(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="UZS")
    frequency: Mapped[str] = mapped_column(String(20))  # daily, weekly, monthly, yearly

    next_charge_date: Mapped[datetime] = mapped_column(DateTime)
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=2)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(id={self.id}, name={self.name}, amount={self.amount})>"
