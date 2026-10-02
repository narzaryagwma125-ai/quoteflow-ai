from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

QUOTE_STATUSES = ("draft", "sent", "viewed", "accepted", "rejected", "expired", "cancelled")


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (
        # Quote numbers must be unique per business (user).
        UniqueConstraint("user_id", "quote_number", name="uq_quotes_user_quote_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    quote_number: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    subtotal_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    terms: Mapped[str] = mapped_column(Text, nullable=False, default="")
    public_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    public_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # customer-supplied acceptance metadata
    responded_by_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    responded_by_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="quotes")
    customer = relationship("Customer", back_populates="quotes")
    items = relationship(
        "QuoteItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteItem.sort_order",
        lazy="selectin",
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), index=True, nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    unit_price_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    line_total_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    quote = relationship("Quote", back_populates="items")
