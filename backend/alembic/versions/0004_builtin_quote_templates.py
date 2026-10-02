"""add five built-in quotation template styles

Revision ID: 0004_builtin_quote_templates
Revises: 0003_docx_template
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0004_builtin_quote_templates"
down_revision: Union[str, None] = "0003_docx_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Existing "default" users become the Classic built-in template.
    op.execute("UPDATE business_profiles SET template_type = 'classic' WHERE template_type = 'default' OR template_type IS NULL")

def downgrade() -> None:
    op.execute("UPDATE business_profiles SET template_type = 'default' WHERE template_type IN ('classic','modern','minimal','executive','creative')")
