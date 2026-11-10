"""add categories to recipes

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-11-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, Sequence[str], None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('recipes', sa.Column('categories', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('recipes', 'categories')
