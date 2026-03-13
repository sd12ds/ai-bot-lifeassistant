"""favorites_and_templates

Revision ID: ac751ed9ccf6
Revises: 03ebc98a7ffc
Create Date: 2026-03-11 13:09:01.025360

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ac751ed9ccf6'
down_revision: Union[str, None] = '03ebc98a7ffc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Создание таблиц: favorite_foods, meal_templates, meal_template_items."""
    op.create_table('meal_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('meal_type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.telegram_id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('favorite_foods',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('food_item_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['food_item_id'], ['food_items.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.telegram_id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'food_item_id', name='uq_favorite_user_food'),
    )
    op.create_table('meal_template_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=False),
        sa.Column('food_item_id', sa.Integer(), nullable=False),
        sa.Column('amount_g', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['food_item_id'], ['food_items.id']),
        sa.ForeignKeyConstraint(['template_id'], ['meal_templates.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Удаление таблиц."""
    op.drop_table('meal_template_items')
    op.drop_table('favorite_foods')
    op.drop_table('meal_templates')
