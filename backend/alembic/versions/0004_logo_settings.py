"""add logo display settings for quotations

Revision ID: 0004_logo_settings
Revises: 0003_docx_template
Create Date: 2026-09-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_logo_settings"
down_revision: Union[str, None] = "0003_docx_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "business_profiles",
        sa.Column("logo_position", sa.String(10), nullable=False, server_default="left"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("logo_size", sa.String(10), nullable=False, server_default="medium"),
    )
    op.add_column(
        "business_profiles",
        sa.Column(
            "show_logo_on_quotation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("business_profiles", "show_logo_on_quotation")
    op.drop_column("business_profiles", "logo_size")
    op.drop_column("business_profiles", "logo_position")