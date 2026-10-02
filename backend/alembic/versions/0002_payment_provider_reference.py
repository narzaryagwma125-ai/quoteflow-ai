"""add generic payment provider reference

Revision ID: 0002_payment_provider_reference
Revises: 0001_initial
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_payment_provider_reference"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("provider_reference_id", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_subscriptions_provider_reference_id",
        "subscriptions",
        ["provider_reference_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscriptions_provider_reference_id",
        table_name="subscriptions",
    )
    op.drop_column("subscriptions", "provider_reference_id")
