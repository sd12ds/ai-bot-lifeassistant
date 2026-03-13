"""profile_body_params_and_goal_type

Revision ID: 03ebc98a7ffc
Revises: d646032113e9
Create Date: 2026-03-11 12:42:47.416539

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '03ebc98a7ffc'
down_revision: Union[str, None] = 'd646032113e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляем поля тела в UserProfile и тип цели в NutritionGoal."""
    # UserProfile — параметры тела для расчёта КБЖУ
    op.add_column('user_profiles', sa.Column('weight_kg', sa.Float(), nullable=True))
    op.add_column('user_profiles', sa.Column('height_cm', sa.Float(), nullable=True))
    op.add_column('user_profiles', sa.Column('age', sa.Integer(), nullable=True))
    op.add_column('user_profiles', sa.Column('gender', sa.String(length=10), nullable=True))
    # NutritionGoal — тип цели и уровень активности
    op.add_column('nutrition_goals', sa.Column('goal_type', sa.String(length=20), nullable=True))
    op.add_column('nutrition_goals', sa.Column('activity_level', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Откат: удаляем добавленные колонки."""
    op.drop_column('nutrition_goals', 'activity_level')
    op.drop_column('nutrition_goals', 'goal_type')
    op.drop_column('user_profiles', 'gender')
    op.drop_column('user_profiles', 'age')
    op.drop_column('user_profiles', 'height_cm')
    op.drop_column('user_profiles', 'weight_kg')
