"""
Фабрики тестовых объектов для coaching-модуля.
"""
from .coaching_factories import (
    GoalFactory,
    HabitFactory,
    HabitLogFactory,
    GoalMilestoneFactory,
    GoalCheckinFactory,
    CoachingInsightFactory,
    CoachingRecommendationFactory,
    UserCoachingProfileFactory,
    CoachingMemoryFactory,
)

__all__ = [
    "GoalFactory",
    "HabitFactory",
    "HabitLogFactory",
    "GoalMilestoneFactory",
    "GoalCheckinFactory",
    "CoachingInsightFactory",
    "CoachingRecommendationFactory",
    "UserCoachingProfileFactory",
    "CoachingMemoryFactory",
]
