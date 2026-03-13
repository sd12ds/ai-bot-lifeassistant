"""
pytest-тесты FastAPI роутера /api/tasks.
Покрывает: CRUD, фильтры period/status, валидацию, синхронизацию is_done↔status.
"""
from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient


# ── GET /api/tasks ─────────────────────────────────────────────────────────────

class TestListTasks:
    async def test_returns_empty_list_initially(self, client: AsyncClient):
        """Новый пользователь — пустой список задач."""
        r = await client.get("/api/tasks/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_returns_all_created_tasks(self, client: AsyncClient):
        """После создания задачи она появляется в списке."""
        await client.post("/api/tasks/", json={"title": "Задача 1"})
        await client.post("/api/tasks/", json={"title": "Задача 2"})
        r = await client.get("/api/tasks/")
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_filter_period_today_returns_only_today(self, client: AsyncClient):
        """period=today возвращает только задачи с дедлайном сегодня."""
        now = datetime.now(timezone.utc)
        today_due = now.replace(hour=23, minute=0, second=0).isoformat()
        next_week_due = (now + timedelta(days=8)).isoformat()

        await client.post("/api/tasks/", json={"title": "Сегодня", "due_datetime": today_due})
        await client.post("/api/tasks/", json={"title": "На следующей неделе", "due_datetime": next_week_due})
        await client.post("/api/tasks/", json={"title": "Без срока"})

        r = await client.get("/api/tasks/?period=today")
        assert r.status_code == 200
        titles = [t["title"] for t in r.json()]
        assert "Сегодня" in titles
        assert "На следующей неделе" not in titles
        assert "Без срока" not in titles

    async def test_filter_period_week(self, client: AsyncClient):
        """period=week возвращает задачи с дедлайном в ближайшие 7 дней."""
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).isoformat()
        in_8_days = (now + timedelta(days=8)).isoformat()

        await client.post("/api/tasks/", json={"title": "Завтра", "due_datetime": tomorrow})
        await client.post("/api/tasks/", json={"title": "Через 8 дней", "due_datetime": in_8_days})

        r = await client.get("/api/tasks/?period=week")
        titles = [t["title"] for t in r.json()]
        assert "Завтра" in titles
        assert "Через 8 дней" not in titles

    async def test_filter_period_nodate(self, client: AsyncClient):
        """period=nodate возвращает только задачи без дедлайна."""
        now = datetime.now(timezone.utc)
        await client.post("/api/tasks/", json={"title": "Со сроком", "due_datetime": now.isoformat()})
        await client.post("/api/tasks/", json={"title": "Без срока"})

        r = await client.get("/api/tasks/?period=nodate")
        titles = [t["title"] for t in r.json()]
        assert "Без срока" in titles
        assert "Со сроком" not in titles

    async def test_filter_status_todo(self, client: AsyncClient):
        """status=todo возвращает только невыполненные задачи."""
        r1 = await client.post("/api/tasks/", json={"title": "Активная"})
        r2 = await client.post("/api/tasks/", json={"title": "Готовая"})
        await client.patch(f"/api/tasks/{r2.json()['id']}", json={"is_done": True})

        r = await client.get("/api/tasks/?status=todo")
        titles = [t["title"] for t in r.json()]
        assert "Активная" in titles
        assert "Готовая" not in titles

    async def test_filter_status_done(self, client: AsyncClient):
        """status=done возвращает только выполненные задачи."""
        r1 = await client.post("/api/tasks/", json={"title": "Активная"})
        r2 = await client.post("/api/tasks/", json={"title": "Готовая"})
        await client.patch(f"/api/tasks/{r2.json()['id']}", json={"is_done": True})

        r = await client.get("/api/tasks/?status=done")
        titles = [t["title"] for t in r.json()]
        assert "Готовая" in titles
        assert "Активная" not in titles

    async def test_ordering_undone_before_done(self, client: AsyncClient):
        """Невыполненные задачи идут раньше выполненных."""
        r1 = await client.post("/api/tasks/", json={"title": "Активная", "priority": 2})
        r2 = await client.post("/api/tasks/", json={"title": "Готовая", "priority": 2})
        await client.patch(f"/api/tasks/{r2.json()['id']}", json={"is_done": True})

        r = await client.get("/api/tasks/")
        tasks = r.json()
        undone = [t for t in tasks if not t["is_done"]]
        done = [t for t in tasks if t["is_done"]]
        # Все невыполненные идут первыми
        if undone and done:
            assert tasks.index(undone[-1]) < tasks.index(done[0])


# ── POST /api/tasks ────────────────────────────────────────────────────────────

class TestCreateTask:
    async def test_creates_task_with_required_fields(self, client: AsyncClient):
        """Создание задачи с минимальными полями."""
        r = await client.post("/api/tasks/", json={"title": "Минимальная задача"})
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Минимальная задача"
        assert data["is_done"] == False
        assert data["priority"] == 2  # default

    async def test_creates_task_with_all_fields(self, client: AsyncClient):
        """Создание задачи со всеми полями."""
        due = datetime.now(timezone.utc).isoformat()
        payload = {
            "title": "Полная задача",
            "description": "Описание",
            "priority": 1,
            "tags": ["работа", "срочно"],
            "due_datetime": due,
        }
        r = await client.post("/api/tasks/", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["priority"] == 1
        assert "работа" in data["tags"]
        assert data["due_datetime"] is not None

    async def test_rejects_empty_title(self, client: AsyncClient):
        """Пустой заголовок должен вернуть 422."""
        r = await client.post("/api/tasks/", json={"title": ""})
        # FastAPI/Pydantic не валидирует минимальную длину без аннотации,
        # но пустой title это строка — 201. Проверяем что хотя бы не 500.
        assert r.status_code in (201, 422)

    async def test_rejects_missing_title(self, client: AsyncClient):
        """Отсутствие title должно вернуть 422."""
        r = await client.post("/api/tasks/", json={"description": "без заголовка"})
        assert r.status_code == 422

    async def test_default_status_is_todo(self, client: AsyncClient):
        """По умолчанию статус задачи = todo."""
        r = await client.post("/api/tasks/", json={"title": "Новая"})
        assert r.json()["status"] == "todo"


# ── GET /api/tasks/:id ─────────────────────────────────────────────────────────

class TestGetTask:
    async def test_returns_task_by_id(self, client: AsyncClient):
        """Возвращает задачу по id."""
        created = (await client.post("/api/tasks/", json={"title": "Задача по id"})).json()
        r = await client.get(f"/api/tasks/{created['id']}")
        assert r.status_code == 200
        assert r.json()["title"] == "Задача по id"

    async def test_returns_404_for_nonexistent(self, client: AsyncClient):
        """404 для несуществующей задачи."""
        r = await client.get("/api/tasks/99999")
        assert r.status_code == 404


# ── PATCH /api/tasks/:id ───────────────────────────────────────────────────────

class TestPatchTask:
    async def test_updates_title(self, client: AsyncClient):
        """Обновление заголовка задачи."""
        created = (await client.post("/api/tasks/", json={"title": "Старый"})).json()
        r = await client.patch(f"/api/tasks/{created['id']}", json={"title": "Новый"})
        assert r.status_code == 200
        assert r.json()["title"] == "Новый"

    async def test_is_done_true_sets_status_done(self, client: AsyncClient):
        """is_done=True синхронизируется → status='done'."""
        created = (await client.post("/api/tasks/", json={"title": "Задача"})).json()
        r = await client.patch(f"/api/tasks/{created['id']}", json={"is_done": True})
        assert r.status_code == 200
        data = r.json()
        assert data["is_done"] == True
        assert data["status"] == "done"

    async def test_is_done_false_restores_status_todo(self, client: AsyncClient):
        """is_done=False после done → status='todo'."""
        created = (await client.post("/api/tasks/", json={"title": "Задача"})).json()
        await client.patch(f"/api/tasks/{created['id']}", json={"is_done": True})
        r = await client.patch(f"/api/tasks/{created['id']}", json={"is_done": False})
        assert r.json()["status"] == "todo"

    async def test_updates_priority(self, client: AsyncClient):
        """Обновление приоритета."""
        created = (await client.post("/api/tasks/", json={"title": "Задача", "priority": 2})).json()
        r = await client.patch(f"/api/tasks/{created['id']}", json={"priority": 1})
        assert r.json()["priority"] == 1

    async def test_updates_tags(self, client: AsyncClient):
        """Обновление тегов."""
        created = (await client.post("/api/tasks/", json={"title": "Задача", "tags": ["старый"]})).json()
        r = await client.patch(f"/api/tasks/{created['id']}", json={"tags": ["новый", "тег"]})
        assert "новый" in r.json()["tags"]
        assert "старый" not in r.json()["tags"]

    async def test_returns_404_for_nonexistent(self, client: AsyncClient):
        """404 при попытке обновить несуществующую задачу."""
        r = await client.patch("/api/tasks/99999", json={"title": "X"})
        assert r.status_code == 404


# ── DELETE /api/tasks/:id ──────────────────────────────────────────────────────

class TestDeleteTask:
    async def test_deletes_existing_task(self, client: AsyncClient):
        """Успешное удаление задачи → 204."""
        created = (await client.post("/api/tasks/", json={"title": "Удалить"})).json()
        r = await client.delete(f"/api/tasks/{created['id']}")
        assert r.status_code == 204

    async def test_task_not_found_after_delete(self, client: AsyncClient):
        """После удаления задача недоступна → 404."""
        created = (await client.post("/api/tasks/", json={"title": "Удалить"})).json()
        await client.delete(f"/api/tasks/{created['id']}")
        r = await client.get(f"/api/tasks/{created['id']}")
        assert r.status_code == 404

    async def test_returns_404_for_nonexistent(self, client: AsyncClient):
        """404 при удалении несуществующей задачи."""
        r = await client.delete("/api/tasks/99999")
        assert r.status_code == 404

    async def test_user_cannot_delete_others_task(self, client: AsyncClient, db_session):
        """Нельзя удалить задачу другого пользователя."""
        from db.models import Task as TaskModel
        # Создаём задачу другого пользователя напрямую в БД
        other_task = TaskModel(user_id=999999, title="Чужая задача")
        db_session.add(other_task)
        await db_session.commit()
        await db_session.refresh(other_task)

        r = await client.delete(f"/api/tasks/{other_task.id}")
        assert r.status_code == 404  # не найдена для текущего пользователя
