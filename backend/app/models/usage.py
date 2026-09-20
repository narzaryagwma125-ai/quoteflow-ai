from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UsageCounter(Base):
    """Monthly usage counter per user per feature (e.g. quotes, ai)."""

    __tablename__ = "usage_counters"
    __table_args__ = (
        UniqueConstraint("user_id", "feature", "period", name="uq_usage_user_feature_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    feature: Mapped[str] = mapped_column(String(20), nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # e.g. "2026-09"
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="usage")
