from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

PLANS = ("free", "starter", "pro", "business")
SUBSCRIPTION_STATUSES = (
    "active",
    "trialing",
    "past_due",
    "canceled",
    "unpaid",
    "incomplete",
)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(20), default="razorpay", nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="subscriptions")
