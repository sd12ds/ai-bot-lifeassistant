"""
Fixtures для E2E тестов coaching.
Переиспользуем фикстуры из tests/coaching/conftest.py.
"""
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Goal, User
from tests.factories.coaching_factories import GoalFactory


@pytest_asyncio.fixture
async def one_goal(db_session: AsyncSession, test_user: User) -> Goal:
    """Создаёт одну тестовую цель для E2E тестов."""
    goal = GoalFactory.build(
        user_id=test_user.telegram_id,
        title="E2E Test Goal",
        area="productivity",
        status="active",
        progress_pct=0,
    )
    db_session.add(goal)
    await db_session.commit()
    await db_session.refresh(goal)
    return goal
