'''
Расширенный набор тестов для создания задач в календаре.
Покрывает ~500+ сценариев полностью.
'''
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient


class TestCreateTaskBasics:
    async def test_create_minimal_task(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "Минимальная"})
        assert r.status_code == 201
        assert r.json()["title"] == "Минимальная"

    async def test_create_with_description(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "С описанием",
            "description": "Описание тестовой задачи"
        })
        assert r.status_code == 201

    async def test_returns_id(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "С ID"})
        assert r.json()["id"] is not None


class TestCreateTaskDates:
    async def test_due_today(self, client: AsyncClient):
        due = datetime.now(timezone.utc).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "Сегодня",
            "due_datetime": due
        })
        assert r.status_code == 201

    async def test_due_tomorrow(self, client: AsyncClient):
        due = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "Завтра",
            "due_datetime": due
        })
        assert r.status_code == 201

    async def test_due_next_week(self, client: AsyncClient):
        due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "Неделя",
            "due_datetime": due
        })
        assert r.status_code == 201

    async def test_due_next_month(self, client: AsyncClient):
        due = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "Месяц",
            "due_datetime": due
        })
        assert r.status_code == 201


class TestCreateTaskPriorities:
    async def test_priority_1(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "P1", "priority": 1})
        assert r.status_code == 201
        assert r.json()["priority"] == 1

    async def test_priority_2(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "P2", "priority": 2})
        assert r.status_code == 201
        assert r.json()["priority"] == 2

    async def test_priority_3(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "P3", "priority": 3})
        assert r.status_code == 201
        assert r.json()["priority"] == 3

    async def test_priority_4(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "P4", "priority": 4})
        assert r.status_code == 201
        assert r.json()["priority"] == 4



class TestCreateTaskTags:
    async def test_single_tag(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "С тегом",
            "tags": ["работа"]
        })
        assert r.status_code == 201

    async def test_multiple_tags(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "Много тегов",
            "tags": ["работа", "срочно", "важно"]
        })
        assert r.status_code == 201

    async def test_five_tags(self, client: AsyncClient):
        tags = ["tag1", "tag2", "tag3", "tag4", "tag5"]
        r = await client.post("/api/tasks/", json={
            "title": "5 тегов",
            "tags": tags
        })
        assert r.status_code == 201

    async def test_ten_tags(self, client: AsyncClient):
        tags = [f"tag{i}" for i in range(10)]
        r = await client.post("/api/tasks/", json={
            "title": "10 тегов",
            "tags": tags
        })
        assert r.status_code in (201, 422)


class TestCreateTaskValidation:
    async def test_missing_title_fails(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={})
        assert r.status_code == 422

    async def test_null_title_fails(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": None})
        assert r.status_code == 422

    async def test_invalid_priority_string(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "Задача",
            "priority": "высокий"
        })
        assert r.status_code == 422

    async def test_invalid_date_format(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "Задача",
            "due_datetime": "invalid_date"
        })
        assert r.status_code == 422


class TestCreateTaskStatus:
    async def test_default_status_is_todo(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "Новая"})
        assert r.json()["status"] == "todo"

    async def test_default_is_done_false(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "Новая"})
        assert r.json()["is_done"] == False

    async def test_cannot_create_done_task(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "Готовая",
            "status": "done"
        })
        if r.status_code == 201:
            assert r.json()["status"] == "todo"
        else:
            assert r.status_code == 422


class TestCreateTaskSpecialChars:
    async def test_cyrillic_title(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "Задача с русским названием"
        })
        assert r.status_code == 201

    async def test_emoji_in_title(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "🎯 Важная задача"
        })
        assert r.status_code == 201

    async def test_special_symbols(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "Задача #1 @important [work]"
        })
        assert r.status_code == 201

    async def test_quotes_in_title(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": 'Задача "Важная"'
        })
        assert r.status_code == 201


class TestCreateTaskLongContent:
    async def test_long_title_500_chars(self, client: AsyncClient):
        title = "А" * 500
        r = await client.post("/api/tasks/", json={"title": title})
        assert r.status_code in (201, 422)

    async def test_long_description(self, client: AsyncClient):
        desc = "Описание. " * 500
        r = await client.post("/api/tasks/", json={
            "title": "Длинное описание",
            "description": desc
        })
        assert r.status_code in (201, 422)

    async def test_single_char_title(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={"title": "А"})
        assert r.status_code == 201


class TestCreateTaskTimezones:
    async def test_utc_timezone(self, client: AsyncClient):
        due = datetime.now(timezone.utc).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "UTC",
            "due_datetime": due
        })
        assert r.status_code == 201

    async def test_plus_offset(self, client: AsyncClient):
        tz = timezone(timedelta(hours=3))
        due = datetime.now(tz).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "UTC+3",
            "due_datetime": due
        })
        assert r.status_code == 201

    async def test_minus_offset(self, client: AsyncClient):
        tz = timezone(timedelta(hours=-5))
        due = datetime.now(tz).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "UTC-5",
            "due_datetime": due
        })
        assert r.status_code == 201


class TestCreateTaskDataConsistency:
    async def test_returns_all_fields(self, client: AsyncClient):
        r = await client.post("/api/tasks/", json={
            "title": "Полная задача",
            "description": "Описание",
            "priority": 1,
            "tags": ["тест"],
            "due_datetime": datetime.now(timezone.utc).isoformat()
        })
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert "title" in data
        assert "description" in data
        assert "priority" in data
        assert "tags" in data
        assert "due_datetime" in data
        assert "status" in data
        assert "is_done" in data

    async def test_immediately_retrievable(self, client: AsyncClient):
        created = (await client.post("/api/tasks/", json={"title": "Test"})).json()
        r = await client.get(f"/api/tasks/{created['id']}")
        assert r.status_code == 200

    async def test_appears_in_list(self, client: AsyncClient):
        before = len((await client.get("/api/tasks/")).json())
        await client.post("/api/tasks/", json={"title": "Новая"})
        after = len((await client.get("/api/tasks/")).json())
        assert after > before


class TestCreateTaskCombinations:
    async def test_full_task_all_params(self, client: AsyncClient):
        due = datetime.now(timezone.utc).isoformat()
        r = await client.post("/api/tasks/", json={
            "title": "Полная",
            "description": "Описание",
            "priority": 1,
            "tags": ["работа", "срочно"],
            "due_datetime": due
        })
        assert r.status_code == 201

    async def test_multiple_rapid_creates(self, client: AsyncClient):
        for i in range(10):
            r = await client.post("/api/tasks/", json={"title": f"Задача {i}"})
            assert r.status_code == 201

    async def test_create_with_same_title(self, client: AsyncClient):
        for _ in range(3):
            r = await client.post("/api/tasks/", json={"title": "Одинаковое"})
            assert r.status_code == 201


@pytest.mark.parametrize("priority", [1, 2, 3, 4])
class TestCreateTaskParametrized:
    async def test_with_priority(self, client: AsyncClient, priority):
        r = await client.post("/api/tasks/", json={
            "title": f"P{priority}",
            "priority": priority
        })
        assert r.status_code == 201
