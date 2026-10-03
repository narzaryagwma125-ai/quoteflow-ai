"""merge migration heads

Revision ID: 572cb99d597c
Revises: 0002_payment_provider_reference, 0004_builtin_quote_templates, 0005_currency_default_inr
Create Date: 2026-10-03 11:55:30.845883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '572cb99d597c'
down_revision: Union[str, None] = ('0002_payment_provider_reference', '0004_builtin_quote_templates', '0005_currency_default_inr')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass