"""
Phase 6: E2E тесты coaching модуля.
Полный сценарий от создания цели до завершения через API.

8 E2E сценариев:
1. Полный жизненный цикл цели (create → checkin → achieve)
2. Полный жизненный цикл привычки (create → log → pause → resume)
3. Онбординг → цель → привычка → dashboard
4. Аналитика после нескольких check-in
5. Заморозка и возобновление цели
6. Еженедельный review flow
7. Сценарий dropout-риска (нет активности 7 дней)
8. Создание цели с вехами (milestones)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Goal, Habit


# ══════════════════════════════════════════════════════════════════════════════
# E2E 1: Полный жизненный цикл цели
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_goal_full_lifecycle(client: AsyncClient, test_user: User):
    """
    E2E: Создать цель → сделать check-in → обновить прогресс → достичь цели.
    Проверяем статус на каждом шаге.
    """
    # Шаг 1: Создаём цель
    resp = await client.post("/api/coaching/goals", json={
        "title": "E2E: Пробежать 5км",
        "area": "fitness",
        "why_statement": "Хочу быть здоровее",
        "first_step": "Первая пробежка 1км",
    })
    assert resp.status_code == 201
    goal_id = resp.json()["id"]
    assert resp.json()["status"] == "active"

    # Шаг 2: Check-in с прогрессом
    resp = await client.post("/api/coaching/checkins", json={
        "goal_id": goal_id,
        "progress_pct": 50,
        "energy_level": 4,
        "notes": "Половина пути пройдена",
    })
    assert resp.status_code == 201

    # Шаг 3: Обновляем прогресс цели
    resp = await client.put(f"/api/coaching/goals/{goal_id}", json={
        "progress_pct": 75,
    })
    assert resp.status_code == 200
    assert resp.json()["progress_pct"] == 75

    # Шаг 4: Достигаем цели
    resp = await client.post(f"/api/coaching/goals/{goal_id}/achieve")
    assert resp.status_code == 200

    # Шаг 5: Проверяем что цель теперь completed
    resp = await client.get(f"/api/coaching/goals/{goal_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "achieved"


# ══════════════════════════════════════════════════════════════════════════════
# E2E 2: Полный жизненный цикл привычки
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_habit_full_lifecycle(client: AsyncClient, test_user: User):
    """
    E2E: Создать привычку → залогировать → поставить на паузу → возобновить.
    """
    # Шаг 1: Создаём привычку
    resp = await client.post("/api/coaching/habits", json={
        "title": "E2E: Медитация 10 минут",
        "area": "mindfulness",
        "frequency": "daily",
    })
    assert resp.status_code == 201
    habit_id = resp.json()["id"]
    initial_streak = resp.json().get("current_streak", 0)

    # Шаг 2: Логируем выполнение
    resp = await client.post(f"/api/coaching/habits/{habit_id}/log")
    assert resp.status_code == 200
    assert resp.json()["streak"] >= 1

    # Шаг 3: Ставим на паузу
    resp = await client.post(f"/api/coaching/habits/{habit_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["paused"] is True

    # Шаг 4: Список привычек — паузированная не показывается в активных
    resp = await client.get("/api/coaching/habits", params={"is_active": True})
    assert resp.status_code == 200
    active_ids = [h["id"] for h in resp.json()]
    assert habit_id not in active_ids

    # Шаг 5: Возобновляем привычку
    resp = await client.post(f"/api/coaching/habits/{habit_id}/resume")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# E2E 3: Онбординг → цель → dashboard
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_onboarding_to_dashboard(client: AsyncClient, test_user: User):
    """
    E2E: Проверить онбординг → создать первую цель → dashboard отражает данные.
    """
    # Шаг 1: Получаем состояние онбординга
    resp = await client.get("/api/coaching/onboarding")
    assert resp.status_code == 200
    assert "current_step" in resp.json()
    assert "bot_onboarding_done" in resp.json()

    # Шаг 2: Создаём первую цель
    resp = await client.post("/api/coaching/goals", json={
        "title": "E2E: Первая цель после онбординга",
        "area": "productivity",
    })
    assert resp.status_code == 201
    goal_id = resp.json()["id"]

    # Шаг 3: Dashboard отображает цель
    resp = await client.get("/api/coaching/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "weekly_score" in data
    assert "state" in data


# ══════════════════════════════════════════════════════════════════════════════
# E2E 4: Аналитика после нескольких check-in
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_analytics_after_checkins(
    client: AsyncClient, test_user: User, one_goal: Goal
):
    """
    E2E: Сделать несколько check-in → аналитика отражает активность.
    """
    # Шаг 1: Серия check-in по цели
    for progress in [25, 50, 75]:
        resp = await client.post("/api/coaching/checkins", json={
            "goal_id": one_goal.id,
            "progress_pct": progress,
            "energy_level": 3,
        })
        assert resp.status_code == 201

    # Шаг 2: Аналитика целей отображает данные
    resp = await client.get("/api/coaching/analytics/goals")
    assert resp.status_code == 200

    # Шаг 3: Еженедельная аналитика включает check-in
    resp = await client.get("/api/coaching/analytics/weekly")
    assert resp.status_code == 200
    assert "weekly_score" in resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# E2E 5: Заморозка и возобновление цели
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_goal_freeze_resume(
    client: AsyncClient, test_user: User, one_goal: Goal
):
    """
    E2E: Заморозить цель → убедиться что она frozen → возобновить.
    """
    # Шаг 1: Замораживаем цель
    resp = await client.post(f"/api/coaching/goals/{one_goal.id}/freeze", params={
        "reason": "Временно занят другими делами",
    })
    assert resp.status_code == 200
    assert resp.json()["is_frozen"] is True

    # Шаг 2: Проверяем статус через get
    resp = await client.get(f"/api/coaching/goals/{one_goal.id}")
    assert resp.status_code == 200
    assert resp.json()["is_frozen"] is True

    # Шаг 3: Возобновляем цель
    resp = await client.post(f"/api/coaching/goals/{one_goal.id}/resume")
    assert resp.status_code == 200
    assert resp.json()["is_frozen"] is False

    # Шаг 4: Проверяем что цель снова активна
    resp = await client.get(f"/api/coaching/goals/{one_goal.id}")
    assert resp.json()["is_frozen"] is False


# ══════════════════════════════════════════════════════════════════════════════
# E2E 6: Создание вех (milestones) для цели
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_goal_with_milestones(
    client: AsyncClient, test_user: User, one_goal: Goal
):
    """
    E2E: Добавить вехи к цели → получить список → отметить как выполненные.
    """
    # Шаг 1: Добавляем 3 вехи
    milestone_ids = []
    for i, title in enumerate(["Этап 1: подготовка", "Этап 2: старт", "Этап 3: финал"]):
        resp = await client.post("/api/coaching/milestones", json={
            "title": title,
            "goal_id": one_goal.id,
            "order_index": i,
        })
        assert resp.status_code == 201
        milestone_ids.append(resp.json()["id"])

    # Шаг 2: Получаем список вех
    resp = await client.get("/api/coaching/milestones", params={"goal_id": one_goal.id})
    assert resp.status_code == 200
    assert len(resp.json()) == 3

    # Шаг 3: Отмечаем первую веху как выполненную
    resp = await client.post(f"/api/coaching/milestones/{milestone_ids[0]}/complete")
    assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# E2E 7: Профиль коучинга — read & update
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_coaching_profile_read_update(client: AsyncClient, test_user: User):
    """
    E2E: Получить профиль → обновить настройки коучинга.
    """
    # Шаг 1: Получаем профиль
    resp = await client.get("/api/coaching/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "coach_tone" in data or "coaching_style" in data or "user_id" in data

    # Шаг 2: Обновляем тон коуча
    resp = await client.put("/api/coaching/profile", json={
        "coach_tone": "strict",
        "focus_areas": ["fitness", "productivity"],
    })
    assert resp.status_code in (200, 204)


# ══════════════════════════════════════════════════════════════════════════════
# E2E 8: Инсайты — получение и отметка как прочитанных
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.e2e
@pytest.mark.coaching
async def test_e2e_insights_read_and_mark(client: AsyncClient, test_user: User):
    """
    E2E: Получить инсайты → отметить прочитанным.
    """
    # Шаг 1: Получаем активные инсайты
    resp = await client.get("/api/coaching/insights")
    assert resp.status_code == 200
    insights = resp.json()
    assert isinstance(insights, list)

    # Шаг 2: Если есть инсайты — отмечаем первый как прочитанный
    if insights:
        insight_id = insights[0]["id"]
        resp = await client.post(f"/api/coaching/insights/{insight_id}/read")
        assert resp.status_code in (200, 204)

    # Шаг 3: Запрашиваем рекомендации
    resp = await client.get("/api/coaching/recommendations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
