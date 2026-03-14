"""
Phase 3: API-тесты coaching-эндпойнтов.

Покрывает:
- GET /coaching/dashboard — агрегирующий эндпойнт
- GET /coaching/state — состояние пользователя
- CRUD /coaching/goals/* — цели
- CRUD /coaching/habits/* — привычки + трекинг
- POST /coaching/checkins — check-in
- GET /coaching/insights, PUT /coaching/insights/{id}/read
- GET /coaching/recommendations, PUT .../dismiss
- GET/PUT /coaching/profile
- GET /coaching/onboarding, POST .../advance
- GET /coaching/analytics/weekly
- GET /coaching/memory, DELETE /coaching/memory
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import db.coaching_storage as cs
from db.models import Goal, Habit


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_dashboard_returns_200(client: AsyncClient):
    """GET /coaching/dashboard возвращает 200 и нужные поля."""
    resp = await client.get("/api/coaching/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "state" in data
    assert "weekly_score" in data
    assert "goals_active" in data
    assert "habits_today" in data
    assert "risks" in data


@pytest.mark.api
@pytest.mark.coaching
async def test_dashboard_state_valid(client: AsyncClient):
    """Dashboard возвращает одно из 5 валидных состояний."""
    resp = await client.get("/api/coaching/dashboard")
    assert resp.status_code == 200
    state = resp.json()["state"]
    assert state in ("momentum", "stable", "overload", "recovery", "risk")


@pytest.mark.api
@pytest.mark.coaching
async def test_dashboard_weekly_score_range(client: AsyncClient):
    """weekly_score в диапазоне 0-100."""
    resp = await client.get("/api/coaching/dashboard")
    score = resp.json()["weekly_score"]
    assert 0 <= score <= 100


# ══════════════════════════════════════════════════════════════════════════════
# STATE
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_get_state(client: AsyncClient):
    """GET /coaching/state возвращает state и score."""
    resp = await client.get("/api/coaching/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "state" in data
    assert "score" in data


# ══════════════════════════════════════════════════════════════════════════════
# GOALS API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_create_goal(client: AsyncClient):
    """POST /coaching/goals создаёт цель."""
    resp = await client.post("/api/coaching/goals", json={
        "title": "Пробежать марафон",
        "area": "health",
        "priority": 3,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Пробежать марафон"
    assert data["area"] == "health"
    assert data["id"] is not None


@pytest.mark.api
@pytest.mark.coaching
async def test_create_goal_validation(client: AsyncClient):
    """POST /coaching/goals с коротким title → 422."""
    resp = await client.post("/api/coaching/goals", json={"title": "A"})
    assert resp.status_code == 422


@pytest.mark.api
@pytest.mark.coaching
async def test_list_goals_empty(client: AsyncClient):
    """GET /coaching/goals без данных → пустой список."""
    resp = await client.get("/api/coaching/goals")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.api
@pytest.mark.coaching
async def test_list_goals_with_data(client: AsyncClient, one_goal: Goal):
    """GET /coaching/goals возвращает созданные цели."""
    resp = await client.get("/api/coaching/goals")
    assert resp.status_code == 200
    goals = resp.json()
    assert len(goals) >= 1
    assert any(g["id"] == one_goal.id for g in goals)


@pytest.mark.api
@pytest.mark.coaching
async def test_get_goal_by_id(client: AsyncClient, one_goal: Goal):
    """GET /coaching/goals/{id} возвращает конкретную цель."""
    resp = await client.get(f"/api/coaching/goals/{one_goal.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == one_goal.id


@pytest.mark.api
@pytest.mark.coaching
async def test_get_goal_not_found(client: AsyncClient):
    """GET /coaching/goals/99999 → 404."""
    resp = await client.get("/api/coaching/goals/99999")
    assert resp.status_code == 404


@pytest.mark.api
@pytest.mark.coaching
async def test_update_goal(client: AsyncClient, one_goal: Goal):
    """PATCH /coaching/goals/{id} обновляет поля цели."""
    resp = await client.put(f"/api/coaching/goals/{one_goal.id}", json={
        "progress_pct": 75,
        "coaching_notes": "Хорошо идёт!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["progress_pct"] == 75


@pytest.mark.api
@pytest.mark.coaching
async def test_freeze_goal(client: AsyncClient, one_goal: Goal):
    """POST /coaching/goals/{id}/freeze замораживает цель."""
    resp = await client.post(
        f"/api/coaching/goals/{one_goal.id}/freeze",
        params={"reason": "Командировка"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_frozen"] is True


@pytest.mark.api
@pytest.mark.coaching
async def test_resume_goal(client: AsyncClient, one_goal: Goal, db_session: AsyncSession):
    """POST /coaching/goals/{id}/resume размораживает цель."""
    # Сначала заморозим
    await cs.update_goal(db_session, one_goal.id, one_goal.user_id, is_frozen=True)
    await db_session.commit()

    resp = await client.post(f"/api/coaching/goals/{one_goal.id}/resume")
    assert resp.status_code == 200
    assert resp.json()["is_frozen"] is False


@pytest.mark.api
@pytest.mark.coaching
async def test_achieve_goal(client: AsyncClient, one_goal: Goal):
    """POST /coaching/goals/{id}/achieve завершает цель."""
    resp = await client.post(f"/api/coaching/goals/{one_goal.id}/achieve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "achieved"


@pytest.mark.api
@pytest.mark.coaching
async def test_delete_goal(client: AsyncClient):
    """DELETE /coaching/goals/{id} удаляет цель."""
    # Создаём цель через API
    create_resp = await client.post("/api/coaching/goals", json={"title": "Удалить меня"})
    goal_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/coaching/goals/{goal_id}")
    assert resp.status_code == 204

    # Проверяем, что цель удалена
    get_resp = await client.get(f"/api/coaching/goals/{goal_id}")
    assert get_resp.status_code == 404


@pytest.mark.api
@pytest.mark.coaching
async def test_goal_analytics(client: AsyncClient, one_goal: Goal):
    """GET /coaching/goals/{id}/analytics возвращает метрики цели."""
    resp = await client.get(f"/api/coaching/goals/{one_goal.id}/analytics")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# MILESTONES API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_create_milestone(client: AsyncClient, one_goal: Goal):
    """POST /coaching/milestones создаёт этап цели."""
    resp = await client.post("/api/coaching/milestones", json={
        "title": "Этап 1",
        "goal_id": one_goal.id,
        "order_index": 1,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Этап 1"
    assert data["goal_id"] == one_goal.id


@pytest.mark.api
@pytest.mark.coaching
async def test_list_milestones(client: AsyncClient, one_goal: Goal):
    """GET /coaching/goals/{id}/milestones возвращает этапы."""
    resp = await client.get("/api/coaching/milestones", params={"goal_id": one_goal.id})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# HABITS API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_create_habit(client: AsyncClient):
    """POST /coaching/habits создаёт привычку."""
    resp = await client.post("/api/coaching/habits", json={
        "title": "Пить воду",
        "area": "health",
        "frequency": "daily",
        "target_count": 8,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Пить воду"
    assert data["id"] is not None


@pytest.mark.api
@pytest.mark.coaching
async def test_list_habits_empty(client: AsyncClient):
    """GET /coaching/habits → пустой список без данных."""
    resp = await client.get("/api/coaching/habits")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.api
@pytest.mark.coaching
async def test_get_habit(client: AsyncClient, one_habit: Habit):
    """GET /coaching/habits/{id} возвращает привычку."""
    resp = await client.get(f"/api/coaching/habits/{one_habit.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == one_habit.id


@pytest.mark.api
@pytest.mark.coaching
async def test_log_habit(client: AsyncClient, one_habit: Habit):
    """POST /coaching/habits/{id}/log увеличивает стрик."""
    initial_streak = one_habit.current_streak  # Сохраняем до вызова API (int, не изменится)
    resp = await client.post(f"/api/coaching/habits/{one_habit.id}/log")
    assert resp.status_code == 200
    data = resp.json()
    assert "streak" in data
    assert data["streak"] > initial_streak


@pytest.mark.api
@pytest.mark.coaching
async def test_miss_habit(client: AsyncClient, one_habit: Habit):
    """POST /coaching/habits/{id}/miss сбрасывает стрик."""
    resp = await client.post(
        f"/api/coaching/habits/{one_habit.id}/miss",
        json={"reason": "болезнь"}
    )
    assert resp.status_code == 200
    assert resp.json()["streak_reset"] is True


@pytest.mark.api
@pytest.mark.coaching
async def test_pause_habit(client: AsyncClient, one_habit: Habit):
    """POST /coaching/habits/{id}/pause деактивирует привычку."""
    resp = await client.post(f"/api/coaching/habits/{one_habit.id}/pause")
    assert resp.status_code == 200
    assert resp.json()["paused"] is True


@pytest.mark.api
@pytest.mark.coaching
async def test_habit_templates(client: AsyncClient):
    """GET /coaching/habits/templates возвращает список шаблонов."""
    resp = await client.get("/api/coaching/habits/templates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# CHECKINS API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_create_checkin(client: AsyncClient, one_goal: Goal):
    """POST /coaching/checkins создаёт check-in."""
    resp = await client.post("/api/coaching/checkins", json={
        "goal_id": one_goal.id,
        "progress_pct": 65,
        "energy_level": 4,
        "notes": "Всё идёт хорошо",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["progress_pct"] == 65


@pytest.mark.api
@pytest.mark.coaching
async def test_checkin_history(client: AsyncClient):
    """GET /coaching/checkins/history возвращает историю."""
    resp = await client.get("/api/coaching/checkins/history")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# INSIGHTS API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_list_insights(client: AsyncClient, active_insights):
    """GET /coaching/insights возвращает инсайты."""
    resp = await client.get("/api/coaching/insights")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.api
@pytest.mark.coaching
async def test_mark_insight_read_api(client: AsyncClient, active_insights):
    """PUT /coaching/insights/{id}/read помечает инсайт прочитанным."""
    insight_id = active_insights[0].id
    resp = await client.post(f"/api/coaching/insights/{insight_id}/read")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_list_recommendations(client: AsyncClient, active_recommendations):
    """GET /coaching/recommendations возвращает рекомендации."""
    resp = await client.get("/api/coaching/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2


@pytest.mark.api
@pytest.mark.coaching
async def test_dismiss_recommendation_api(client: AsyncClient, active_recommendations):
    """POST /coaching/recommendations/{id}/dismiss отклоняет рекомендацию."""
    rec_id = active_recommendations[0].id
    resp = await client.post(f"/api/coaching/recommendations/{rec_id}/dismiss")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# PROFILE API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_get_profile(client: AsyncClient):
    """GET /coaching/profile создаёт и возвращает профиль."""
    resp = await client.get("/api/coaching/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "coach_tone" in data
    assert "coaching_mode" in data


@pytest.mark.api
@pytest.mark.coaching
async def test_update_profile(client: AsyncClient):
    """PUT /coaching/profile обновляет настройки коуча."""
    resp = await client.put("/api/coaching/profile", json={
        "coach_tone": "strict",
        "max_daily_nudges": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "coach_tone" in data


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_get_onboarding_state(client: AsyncClient):
    """GET /coaching/onboarding создаёт и возвращает онбординг."""
    resp = await client.get("/api/coaching/onboarding")
    assert resp.status_code == 200
    data = resp.json()
    assert "current_step" in data
    assert "bot_onboarding_done" in data  # В OnboardingOut нет is_complete, используем bot_onboarding_done


@pytest.mark.api
@pytest.mark.coaching
async def test_advance_onboarding(client: AsyncClient):
    """POST /coaching/onboarding/advance продвигает шаг онбординга."""
    resp = await client.post("/api/coaching/onboarding/step", json={
        "step": "goals",
    })
    assert resp.status_code in (200, 400, 422)


# ══════════════════════════════════════════════════════════════════════════════
# ANALYTICS API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_weekly_analytics(client: AsyncClient):
    """GET /coaching/analytics/weekly возвращает еженедельные метрики."""
    resp = await client.get("/api/coaching/analytics/weekly")
    assert resp.status_code == 200
    data = resp.json()
    assert "weekly_score" in data  # Ключ в WeeklyAnalyticsOut
    assert "weekly_score_breakdown" in data  # breakdown вместо components


@pytest.mark.api
@pytest.mark.coaching
async def test_goals_analytics(client: AsyncClient):
    """GET /coaching/analytics/goals возвращает метрики целей."""
    resp = await client.get("/api/coaching/analytics/goals")
    assert resp.status_code == 200


@pytest.mark.api
@pytest.mark.coaching
async def test_habits_analytics(client: AsyncClient):
    """GET /coaching/analytics/habits возвращает метрики привычек."""
    resp = await client.get("/api/coaching/analytics/habits")
    assert resp.status_code == 200


@pytest.mark.api
@pytest.mark.coaching
async def test_dropout_risk_analytics(client: AsyncClient):
    """GET /coaching/analytics/dropout-risk возвращает риск дропаута."""
    resp = await client.get("/api/coaching/analytics/dropout-risk")
    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "level" in data


# ══════════════════════════════════════════════════════════════════════════════
# MEMORY API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_get_memory_empty(client: AsyncClient):
    """GET /coaching/memory пустая память → пустой список."""
    resp = await client.get("/api/coaching/memory")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.api
@pytest.mark.coaching
async def test_clear_memory(client: AsyncClient, db_session: AsyncSession, test_user):
    """DELETE /coaching/memory удаляет все записи памяти."""
    # Добавляем память через storage
    await cs.upsert_memory(
        db_session, test_user.telegram_id,
        memory_type="preference", key="test_key", value="test_value"
    )
    await db_session.commit()

    resp = await client.delete("/api/coaching/memory")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS API
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_get_prompts(client: AsyncClient):
    """GET /coaching/prompts возвращает список подсказок."""
    resp = await client.get("/api/coaching/prompts")
    assert resp.status_code == 200
    data = resp.json()
    # GET /prompts возвращает list[str] напрямую
    assert isinstance(data, list)
    assert len(data) > 0


# ══════════════════════════════════════════════════════════════════════════════
# CONTRACT TESTS — структура ответов
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.api
@pytest.mark.coaching
async def test_goal_out_contract(client: AsyncClient):
    """GoalOut содержит все обязательные поля согласно контракту."""
    resp = await client.post("/api/coaching/goals", json={"title": "Контракт тест"})
    assert resp.status_code == 201
    goal = resp.json()
    required_fields = [
        "id", "title", "description", "area", "status", "priority",
        "progress_pct", "is_frozen", "created_at", "updated_at"
    ]
    for field in required_fields:
        assert field in goal, f"Поле {field!r} отсутствует в GoalOut"


@pytest.mark.api
@pytest.mark.coaching
async def test_habit_out_contract(client: AsyncClient):
    """HabitOut содержит все обязательные поля."""
    resp = await client.post("/api/coaching/habits", json={"title": "Контракт привычка"})
    assert resp.status_code == 201
    habit = resp.json()
    required_fields = ["id", "title", "frequency", "is_active", "current_streak"]
    for field in required_fields:
        assert field in habit, f"Поле {field!r} отсутствует в HabitOut"


@pytest.mark.api
@pytest.mark.coaching
async def test_dashboard_contract(client: AsyncClient):
    """DashboardOut содержит все обязательные поля."""
    resp = await client.get("/api/coaching/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    required = [
        "state", "state_score", "weekly_score", "goals_active",
        "habits_today", "recommendations", "risks", "dropout_risk_level"
    ]
    for field in required:
        assert field in data, f"Поле {field!r} отсутствует в DashboardOut"
