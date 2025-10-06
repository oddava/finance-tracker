from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Numeric, func, Integer, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.crud import Model


class Goal(Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    target_amount: Mapped[float] = mapped_column(Float)
    current_amount: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="UZS")

    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self):
        return f"<Goal(id={self.id}, name={self.name}, progress={self.current_amount}/{self.target_amount})>"
