"""add custom quotation template support

Revision ID: 0002_custom_template
Revises: 0001_initial
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_custom_template"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts_timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "template_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stored_name", sa.String(128), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        *_ts_timestamps(),
    )
    op.create_index("ix_template_files_user_id", "template_files", ["user_id"])
    op.create_index("ix_template_files_stored_name", "template_files", ["stored_name"], unique=True)

    op.add_column(
        "business_profiles",
        sa.Column("template_type", sa.String(20), nullable=False, server_default="default"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_template_file_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_template_filename", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_template_mime_type", sa.String(64), nullable=False, server_default=""),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_template_size", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_template_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_template_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_business_profiles_custom_template_file_id_template_files",
        "business_profiles",
        "template_files",
        ["custom_template_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_business_profiles_custom_template_file_id",
        "business_profiles",
        ["custom_template_file_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_business_profiles_custom_template_file_id", table_name="business_profiles")
    op.drop_constraint(
        "fk_business_profiles_custom_template_file_id_template_files",
        "business_profiles",
        type_="foreignkey",
    )
    op.drop_column("business_profiles", "custom_template_version")
    op.drop_column("business_profiles", "custom_template_uploaded_at")
    op.drop_column("business_profiles", "custom_template_size")
    op.drop_column("business_profiles", "custom_template_mime_type")
    op.drop_column("business_profiles", "custom_template_filename")
    op.drop_column("business_profiles", "custom_template_file_id")
    op.drop_column("business_profiles", "template_type")
    op.drop_index("ix_template_files_stored_name", table_name="template_files")
    op.drop_index("ix_template_files_user_id", table_name="template_files")
    op.drop_table("template_files")