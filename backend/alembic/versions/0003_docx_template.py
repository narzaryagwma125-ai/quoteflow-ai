"""add DOCX custom quotation template support

Revision ID: 0003_docx_template
Revises: 0002_custom_template
Create Date: 2026-09-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_docx_template"
down_revision: Union[str, None] = "0002_custom_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("template_files", "content_type", type_=sa.String(128))

    op.add_column(
        "business_profiles",
        sa.Column("custom_docx_file_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_docx_filename", sa.String(255), nullable=False, server_default=""),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_docx_mime_type", sa.String(128), nullable=False, server_default=""),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_docx_size", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_docx_uploaded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "business_profiles",
        sa.Column("custom_docx_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_business_profiles_custom_docx_file_id_template_files",
        "business_profiles",
        "template_files",
        ["custom_docx_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_business_profiles_custom_docx_file_id",
        "business_profiles",
        ["custom_docx_file_id"],
    )

    op.execute(
        "UPDATE business_profiles SET template_type = 'default' WHERE template_type = 'custom'"
    )


def downgrade() -> None:
    op.drop_index("ix_business_profiles_custom_docx_file_id", table_name="business_profiles")
    op.drop_constraint(
        "fk_business_profiles_custom_docx_file_id_template_files",
        "business_profiles",
        type_="foreignkey",
    )
    op.drop_column("business_profiles", "custom_docx_version")
    op.drop_column("business_profiles", "custom_docx_uploaded_at")
    op.drop_column("business_profiles", "custom_docx_size")
    op.drop_column("business_profiles", "custom_docx_mime_type")
    op.drop_column("business_profiles", "custom_docx_filename")
    op.drop_column("business_profiles", "custom_docx_file_id")
    op.alter_column("template_files", "content_type", type_=sa.String(64))
