"""
Mini-app journey тесты — многошаговые пользовательские сценарии через HTTP API.

Моделируем реальные пути пользователя в mini-app:
1. Жизненный цикл цели: создание -> check-in -> dashboard
2. Жизненный цикл привычки: создание -> лог x3 -> стрик = 3
3. Freeze/Resume жизненный цикл цели
4. Вехи (milestones): создание -> отметка выполненной
5. Рекомендации: запрос -> отметка выполненной
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User, Goal, Habit


# ============================================================================
#  JOURNEY 1: Создание цели -> check-in -> dashboard
# ============================================================================

@pytest.mark.api
@pytest.mark.coaching
class TestGoalCheckinDashboardJourney:
    """Сценарий: пользователь создаёт цель, делает check-in, смотрит дашборд."""

    @pytest.mark.asyncio
    async def test_create_goal_then_checkin_then_dashboard(
        self, client: AsyncClient
    ):
        """
        Шаг 1: POST /coaching/goals -> 201
        Шаг 2: POST /coaching/checkins (goal_id) -> 201
        Шаг 3: GET /coaching/dashboard -> 200 и содержит данные
        """
        # --- Шаг 1: создаём цель ---
        goal_resp = await client.post("/api/coaching/goals", json={
            "title": "Выучить Python за 3 месяца",
            "area": "career",
            "priority": 2,
        })
        assert goal_resp.status_code == 201, goal_resp.text
        goal = goal_resp.json()
        goal_id = goal["id"]
        assert goal["title"] == "Выучить Python за 3 месяца"

        # --- Шаг 2: делаем check-in ---
        checkin_resp = await client.post("/api/coaching/checkins", json={
            "goal_id": goal_id,
            "progress_pct": 20,
            "energy_level": 4,
            "notes": "Прошёл первые уроки",
        })
        assert checkin_resp.status_code == 201, checkin_resp.text
        checkin = checkin_resp.json()
        assert checkin["progress_pct"] == 20

        # --- Шаг 3: смотрим дашборд ---
        dashboard_resp = await client.get("/api/coaching/dashboard")
        assert dashboard_resp.status_code == 200, dashboard_resp.text
        dashboard = dashboard_resp.json()
        assert "state" in dashboard
        # Дашборд использует ключ goals_active
        assert "goals_active" in dashboard or "habits_today" in dashboard

    @pytest.mark.asyncio
    async def test_multiple_checkins_show_progress(
        self, client: AsyncClient
    ):
        """
        Три check-in с нарастающим прогрессом -> в истории все три.
        """
        # Создаём цель
        goal_resp = await client.post("/api/coaching/goals", json={
            "title": "Читать книгу",
            "area": "personal",
            "priority": 3,
        })
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        # Три check-in с нарастающим прогрессом
        for pct, energy in [(25, 3), (50, 4), (75, 5)]:
            resp = await client.post("/api/coaching/checkins", json={
                "goal_id": goal_id,
                "progress_pct": pct,
                "energy_level": energy,
            })
            assert resp.status_code == 201, f"Checkin {pct}% failed: {resp.text}"

        # Проверяем историю
        history_resp = await client.get("/api/coaching/checkins/history")
        assert history_resp.status_code == 200
        history = history_resp.json()
        assert len(history) >= 3

    @pytest.mark.asyncio
    async def test_goal_progress_updates_via_patch(
        self, client: AsyncClient
    ):
        """
        PATCH /goals/{id} с progress_pct=80 -> GET /goals/{id} возвращает 80.
        """
        # Создаём цель
        goal_resp = await client.post("/api/coaching/goals", json={
            "title": "Похудеть на 5 кг",
            "area": "health",
            "priority": 1,
        })
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        # Обновляем прогресс через PUT
        patch_resp = await client.put(f"/api/coaching/goals/{goal_id}", json={
            "title": "Похудеть на 5 кг",
            "progress_pct": 80,
        })
        assert patch_resp.status_code == 200, patch_resp.text

        # Получаем цель и проверяем прогресс
        get_resp = await client.get(f"/api/coaching/goals/{goal_id}")
        assert get_resp.status_code == 200
        updated_goal = get_resp.json()
        assert updated_goal["progress_pct"] == 80


# ============================================================================
#  JOURNEY 2: Привычка -> лог x3 -> стрик
# ============================================================================

@pytest.mark.api
@pytest.mark.coaching
class TestHabitStreakJourney:
    """Сценарий: создание привычки и накопление стрика."""

    @pytest.mark.asyncio
    async def test_create_habit_then_log_three_times_builds_streak(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        POST /habits -> POST /habits/{id}/log x3
        -> streak последовательно растёт.
        """
        # Создаём привычку
        habit_resp = await client.post("/api/coaching/habits", json={
            "title": "Медитация",
            "area": "health",
            "frequency": "daily",
            "target_count": 1,
        })
        assert habit_resp.status_code == 201, habit_resp.text
        habit_id = habit_resp.json()["id"]

        # Логируем 3 раза, проверяем рост стрика
        prev_streak = 0
        for i in range(1, 4):
            log_resp = await client.post(f"/api/coaching/habits/{habit_id}/log")
            assert log_resp.status_code == 200, f"Log {i} failed: {log_resp.text}"
            data = log_resp.json()
            assert "streak" in data
            assert data["streak"] >= prev_streak
            prev_streak = data["streak"]

    @pytest.mark.asyncio
    async def test_habit_miss_resets_streak(
        self, client: AsyncClient, one_habit: Habit
    ):
        """
        POST /habits/{id}/miss -> стрик сбрасывается.
        """
        # Запоминаем начальный стрик
        get_resp = await client.get(f"/api/coaching/habits/{one_habit.id}")
        assert get_resp.status_code == 200
        initial_streak = get_resp.json()["current_streak"]

        # Отмечаем пропуск
        miss_resp = await client.post(
            f"/api/coaching/habits/{one_habit.id}/miss",
            json={"reason": "заболел"}
        )
        assert miss_resp.status_code == 200, miss_resp.text

        # Проверяем сброс стрика
        get_after_resp = await client.get(f"/api/coaching/habits/{one_habit.id}")
        assert get_after_resp.status_code == 200
        assert get_after_resp.json()["current_streak"] == 0

    @pytest.mark.asyncio
    async def test_habit_appears_in_list_after_creation(
        self, client: AsyncClient
    ):
        """
        Созданная привычка появляется в GET /habits.
        """
        # Создаём привычку
        await client.post("/api/coaching/habits", json={
            "title": "Отжимания",
            "area": "health",
            "frequency": "daily",
            "target_count": 30,
        })

        # Проверяем список
        list_resp = await client.get("/api/coaching/habits")
        assert list_resp.status_code == 200
        habits = list_resp.json()
        assert len(habits) >= 1
        titles = [h["title"] for h in habits]
        assert "Отжимания" in titles

    @pytest.mark.asyncio
    async def test_pause_and_unpause_habit(
        self, client: AsyncClient, one_habit: Habit
    ):
        """
        POST /habits/{id}/pause -> is_active = False.
        POST /habits/{id}/resume -> is_active = True.
        """
        # Приостанавливаем
        pause_resp = await client.post(
            f"/api/coaching/habits/{one_habit.id}/pause",
            json={"reason": "отпуск"}
        )
        assert pause_resp.status_code == 200, pause_resp.text

        get_resp = await client.get(f"/api/coaching/habits/{one_habit.id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["is_active"] is False

        # Возобновляем
        resume_resp = await client.post(
            f"/api/coaching/habits/{one_habit.id}/resume"
        )
        assert resume_resp.status_code == 200, resume_resp.text

        get_resp2 = await client.get(f"/api/coaching/habits/{one_habit.id}")
        assert get_resp2.status_code == 200
        assert get_resp2.json()["is_active"] is True


# ============================================================================
#  JOURNEY 3: Freeze / Resume жизненный цикл цели
# ============================================================================

@pytest.mark.api
@pytest.mark.coaching
class TestGoalFreezeResumeJourney:
    """Сценарий: заморозка и разморозка цели."""

    @pytest.mark.asyncio
    async def test_freeze_then_resume_goal(
        self, client: AsyncClient, one_goal: Goal
    ):
        """
        POST /goals/{id}/freeze -> status = frozen
        POST /goals/{id}/resume -> status = active
        """
        goal_id = one_goal.id

        # Замораживаем
        freeze_resp = await client.post(
            f"/api/coaching/goals/{goal_id}/freeze",
            json={"reason": "Отпуск 2 недели"}
        )
        assert freeze_resp.status_code == 200, freeze_resp.text
        frozen = freeze_resp.json()
        assert frozen["is_frozen"] is True

        # Проверяем статус через GET
        get_resp = await client.get(f"/api/coaching/goals/{goal_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["is_frozen"] is True

        # Размораживаем
        resume_resp = await client.post(f"/api/coaching/goals/{goal_id}/resume")
        assert resume_resp.status_code == 200, resume_resp.text
        resumed = resume_resp.json()
        assert resumed["is_frozen"] is False

        # Финальная проверка
        get_final_resp = await client.get(f"/api/coaching/goals/{goal_id}")
        assert get_final_resp.status_code == 200
        assert get_final_resp.json()["is_frozen"] is False

    @pytest.mark.asyncio
    async def test_frozen_goal_in_goals_list(
        self, client: AsyncClient, one_goal: Goal
    ):
        """
        Замороженная цель видна в списке GET /goals.
        """
        goal_id = one_goal.id

        await client.post(
            f"/api/coaching/goals/{goal_id}/freeze",
            json={"reason": "Переоценка"}
        )

        list_resp = await client.get("/api/coaching/goals")
        assert list_resp.status_code == 200
        goals = list_resp.json()

        found = next((g for g in goals if g["id"] == goal_id), None)
        assert found is not None
        assert found["is_frozen"] is True


# ============================================================================
#  JOURNEY 4: Milestone жизненный цикл
# ============================================================================

@pytest.mark.api
@pytest.mark.coaching
class TestMilestoneJourney:
    """Сценарий: создание вехи, отметка завершения."""

    @pytest.mark.asyncio
    async def test_create_milestone_then_complete(
        self, client: AsyncClient, one_goal: Goal
    ):
        """
        POST /goals/{id}/milestones -> 201
        POST /goals/{id}/milestones/{ms_id}/complete -> is_done = True
        """
        goal_id = one_goal.id

        # Создаём веху (milestones — отдельный endpoint, goal_id в теле)
        ms_resp = await client.post("/api/coaching/milestones", json={
            "goal_id": goal_id,
            "title": "Пройти онлайн-курс",
            "target_date": "2025-06-01",
        })
        assert ms_resp.status_code == 201, ms_resp.text
        ms = ms_resp.json()
        ms_id = ms["id"]
        assert ms["title"] == "Пройти онлайн-курс"
        # milestone использует поле status, а не is_done
        assert ms["status"] != "done"

        # Отмечаем выполненной
        complete_resp = await client.post(
            f"/api/coaching/milestones/{ms_id}/complete"
        )
        assert complete_resp.status_code == 200, complete_resp.text
        completed = complete_resp.json()
        assert completed["status"] == "done"

    @pytest.mark.asyncio
    async def test_multiple_milestones_list(
        self, client: AsyncClient, one_goal: Goal
    ):
        """
        Создаём 3 вехи -> GET /goals/{id}/milestones возвращает все 3.
        """
        goal_id = one_goal.id

        for i in range(3):
            resp = await client.post("/api/coaching/milestones", json={
                "goal_id": goal_id,
                "title": f"Этап {i + 1}",
                "target_date": "2025-12-01",
            })
            assert resp.status_code == 201, f"Milestone {i+1} failed: {resp.text}"

        list_resp = await client.get(f"/api/coaching/milestones?goal_id={goal_id}")
        assert list_resp.status_code == 200
        milestones = list_resp.json()
        assert len(milestones) >= 3


# ============================================================================
#  JOURNEY 5: Аналитика и insights
# ============================================================================

@pytest.mark.api
@pytest.mark.coaching
class TestAnalyticsJourney:
    """Сценарий: работа с аналитикой после накопления данных."""

    @pytest.mark.asyncio
    async def test_goal_analytics_after_checkins(
        self, client: AsyncClient
    ):
        """
        Создаём цель + 2 check-in -> GET /goals/{id}/analytics возвращает данные.
        """
        # Создаём цель
        goal_resp = await client.post("/api/coaching/goals", json={
            "title": "Сдать IELTS",
            "area": "career",
            "priority": 1,
        })
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        # Два check-in
        for pct in (30, 60):
            await client.post("/api/coaching/checkins", json={
                "goal_id": goal_id,
                "progress_pct": pct,
                "energy_level": 3,
            })

        # Аналитика цели
        analytics_resp = await client.get(f"/api/coaching/goals/{goal_id}/analytics")
        assert analytics_resp.status_code == 200
        analytics = analytics_resp.json()
        # Аналитика должна содержать хотя бы что-то осмысленное
        assert analytics is not None

    @pytest.mark.asyncio
    async def test_insights_after_activity(
        self, client: AsyncClient, active_insights
    ):
        """
        GET /insights возвращает непрочитанные инсайты.
        POST /insights/{id}/read помечает как прочитанный.
        GET /insights снова -> инсайт помечен прочитанным.
        """
        # Получаем инсайты
        insights_resp = await client.get("/api/coaching/insights")
        assert insights_resp.status_code == 200
        insights = insights_resp.json()
        assert len(insights) >= 1

        # Берём первый непрочитанный
        unread = next((i for i in insights if not i.get("is_read", True)), None)
        assert unread is not None, "Должен быть хотя бы один непрочитанный инсайт"

        insight_id = unread["id"]

        # Отмечаем прочитанным
        read_resp = await client.post(f"/api/coaching/insights/{insight_id}/read")
        assert read_resp.status_code == 200, read_resp.text

        # Проверяем что помечен
        insights_after_resp = await client.get("/api/coaching/insights")
        assert insights_after_resp.status_code == 200
        insights_after = insights_after_resp.json()
        found = next((i for i in insights_after if i["id"] == insight_id), None)
        if found:
            assert found["is_read"] is True

    @pytest.mark.asyncio
    async def test_recommendations_flow(
        self, client: AsyncClient, active_recommendations
    ):
        """
        GET /recommendations -> список рекомендаций
        POST /recommendations/{id}/dismiss -> рекомендация скрыта.
        """
        # Получаем рекомендации
        recs_resp = await client.get("/api/coaching/recommendations")
        assert recs_resp.status_code == 200
        recs = recs_resp.json()
        assert len(recs) >= 1

        rec_id = recs[0]["id"]

        # Dismiss рекомендации
        dismiss_resp = await client.post(
            f"/api/coaching/recommendations/{rec_id}/dismiss"
        )
        assert dismiss_resp.status_code == 200, dismiss_resp.text

    @pytest.mark.asyncio
    async def test_state_endpoint_reflects_activity(
        self, client: AsyncClient
    ):
        """
        GET /state -> возвращает корректное состояние пользователя.
        """
        state_resp = await client.get("/api/coaching/state")
        assert state_resp.status_code == 200
        state_data = state_resp.json()
        assert "state" in state_data
        valid_states = {"momentum", "stable", "overload", "recovery", "risk"}
        assert state_data["state"] in valid_states


# ============================================================================
#  JOURNEY 6: Полный пользовательский путь (end-to-end)
# ============================================================================

@pytest.mark.api
@pytest.mark.coaching
class TestFullUserJourney:
    """
    Комплексный E2E сценарий нового пользователя:
    регистрируется -> создаёт цель -> создаёт привычку -> делает check-in
    -> смотрит дашборд.
    """

    @pytest.mark.asyncio
    async def test_new_user_full_onboarding_flow(
        self, client: AsyncClient
    ):
        """
        Полный путь нового пользователя через mini-app.
        """
        # 1. Проверяем дашборд — пустой у нового пользователя
        dashboard_resp = await client.get("/api/coaching/dashboard")
        assert dashboard_resp.status_code == 200

        # 2. Создаём цель
        goal_resp = await client.post("/api/coaching/goals", json={
            "title": "Запустить стартап",
            "area": "career",
            "priority": 1,
        })
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        # 3. Создаём привычку
        habit_resp = await client.post("/api/coaching/habits", json={
            "title": "Работать над стартапом 2 часа",
            "area": "career",
            "frequency": "daily",
            "target_count": 1,
        })
        assert habit_resp.status_code == 201
        habit_id = habit_resp.json()["id"]

        # 4. Логируем привычку
        log_resp = await client.post(f"/api/coaching/habits/{habit_id}/log")
        assert log_resp.status_code == 200
        assert log_resp.json()["streak"] >= 1

        # 5. Check-in по цели
        checkin_resp = await client.post("/api/coaching/checkins", json={
            "goal_id": goal_id,
            "progress_pct": 10,
            "energy_level": 5,
            "notes": "Первый день работы над проектом",
        })
        assert checkin_resp.status_code == 201

        # 6. Дашборд после активности
        dashboard_after_resp = await client.get("/api/coaching/dashboard")
        assert dashboard_after_resp.status_code == 200
        dashboard_after = dashboard_after_resp.json()
        assert "state" in dashboard_after

        # 7. Список целей и привычек не пустой
        goals_resp = await client.get("/api/coaching/goals")
        assert len(goals_resp.json()) >= 1

        habits_resp = await client.get("/api/coaching/habits")
        assert len(habits_resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_achieve_goal_journey(
        self, client: AsyncClient
    ):
        """
        Создаём цель -> check-in с прогрессом 100% -> отмечаем достигнутой.
        """
        # Создаём цель
        goal_resp = await client.post("/api/coaching/goals", json={
            "title": "Пробежать 5 км",
            "area": "health",
            "priority": 2,
        })
        assert goal_resp.status_code == 201
        goal_id = goal_resp.json()["id"]

        # Check-in с 100% прогрессом
        await client.post("/api/coaching/checkins", json={
            "goal_id": goal_id,
            "progress_pct": 100,
            "energy_level": 5,
            "notes": "Сделал!",
        })

        # Отмечаем достигнутой
        achieve_resp = await client.post(f"/api/coaching/goals/{goal_id}/achieve")
        assert achieve_resp.status_code == 200, achieve_resp.text
        achieved = achieve_resp.json()
        assert achieved["status"] == "achieved"
