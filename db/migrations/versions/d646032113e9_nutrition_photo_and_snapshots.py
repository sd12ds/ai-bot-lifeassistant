"""nutrition_photo_and_snapshots

Revision ID: d646032113e9
Revises: 394157461cc2
Create Date: 2026-03-10 20:32:02.319653

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd646032113e9'
down_revision: Union[str, None] = '394157461cc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет photo_file_id в meals и snapshot-поля КБЖУ в meal_items."""
    op.add_column('meals', sa.Column('photo_file_id', sa.String(length=200), nullable=True))
    op.add_column('meal_items', sa.Column('calories_snapshot', sa.Float(), nullable=True))
    op.add_column('meal_items', sa.Column('protein_snapshot', sa.Float(), nullable=True))
    op.add_column('meal_items', sa.Column('fat_snapshot', sa.Float(), nullable=True))
    op.add_column('meal_items', sa.Column('carbs_snapshot', sa.Float(), nullable=True))


def downgrade() -> None:
    """Откат: удаляем добавленные колонки."""
    op.drop_column('meals', 'photo_file_id')
    op.drop_column('meal_items', 'carbs_snapshot')
    op.drop_column('meal_items', 'fat_snapshot')
    op.drop_column('meal_items', 'protein_snapshot')
    op.drop_column('meal_items', 'calories_snapshot')
