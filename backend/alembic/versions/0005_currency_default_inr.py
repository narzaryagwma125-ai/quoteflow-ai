"""default new quotes and profiles to INR

QuoteFlow now supports INR (₹), USD ($), CAD (CA$), GBP (£) and AUD (A$).
Existing rows keep their stored currency; only the server default changes so
rows created without an explicit currency default to INR.

Uses batch_alter_table so the server-default change also works on SQLite
(which cannot ALTER a column default in place) as well as PostgreSQL.

Revision ID: 0005_currency_default_inr
Revises: 0004_logo_settings
Create Date: 2026-09-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_currency_default_inr"
down_revision: Union[str, None] = "0004_logo_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("business_profiles") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(3),
            server_default="INR",
        )
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(3),
            server_default="INR",
        )


def downgrade() -> None:
    with op.batch_alter_table("business_profiles") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(3),
            server_default="USD",
        )
    with op.batch_alter_table("quotes") as batch_op:
        batch_op.alter_column(
            "currency",
            existing_type=sa.String(3),
            server_default="USD",
        )