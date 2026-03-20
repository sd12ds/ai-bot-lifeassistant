"""
Tools для Research-агента. Привязываются к user_id.
Каждый tool - @tool функция для LangGraph ReAct agent.
"""
from __future__ import annotations

import asyncio
import logging
from langchain_core.tools import tool

from services.research import job_manager
from services.research.execution_engine import run_job

logger = logging.getLogger(__name__)


def make_research_tools(user_id: int):
    """Создает набор tools для research-агента, привязанных к user_id."""

    @tool
    async def create_research_job(
        title: str,
        job_type: str = "search",
        description: str = "",
        urls: str = "",
        extraction_fields: str = "",
    ) -> str:
        """Создает задачу сбора данных из интернета.

        Args:
            title: Название задачи (краткое описание)
            job_type: Тип задачи: search (поиск), crawl (обход сайта), scrape (скрейпинг страниц), extract (извлечение данных)
            description: Подробное описание что нужно найти/собрать
            urls: URL-адреса через запятую (если есть конкретные сайты)
            extraction_fields: Поля для извлечения через запятую (сайт, телефон, email и т.д.)
        """
        # Формируем normalized_spec из параметров
        spec = {"objective": description}
        if urls:
            spec["urls"] = [u.strip() for u in urls.split(",") if u.strip()]
        if extraction_fields:
            fields = [f.strip() for f in extraction_fields.split(",") if f.strip()]
            spec["extraction_schema"] = {f: "string" for f in fields}

        result = await job_manager.create_research_job(
            user_id=user_id,
            title=title,
            job_type=job_type,
            description=description,
            original_request=description,
            normalized_spec=spec,
            origin="chat",
        )
        return f"Задача создана: {result['title']} (ID: {result['id']}, тип: {result['job_type']})"

    @tool
    async def run_research_job(job_id: str) -> str:
        """Запускает созданную задачу на выполнение. Сбор данных происходит в фоне.

        Args:
            job_id: ID задачи для запуска
        """
        # Запуск в фоне - не блокирует чат
        asyncio.create_task(run_job(job_id))
        return f"Задача {job_id} запущена. Сбор данных идет в фоне. Результаты появятся в Research -> Jobs."

    @tool
    async def check_job_status(job_id: str) -> str:
        """Проверяет текущий статус задачи сбора данных.

        Args:
            job_id: ID задачи
        """
        job = await job_manager.get_job(user_id, job_id)
        if not job:
            return "Задача не найдена."
        return f"Задача: {job['title']}\nСтатус: {job['status']}\nТип: {job['job_type']}\nСоздана: {job['created_at']}"

    @tool
    async def list_research_jobs(status_filter: str = "") -> str:
        """Показывает список задач сбора данных.

        Args:
            status_filter: Фильтр по статусу (draft, running, completed, failed) или пусто для всех
        """
        jobs = await job_manager.list_jobs(
            user_id,
            status_filter=status_filter if status_filter else None,
            limit=10,
        )
        if not jobs:
            return "Задач не найдено."
        lines = [f"Найдено задач: {len(jobs)}"]
        for j in jobs:
            lines.append(f"- [{j['status']}] {j['title']} (ID: {j['id'][:8]}...)")
        return "\n".join(lines)

    @tool
    async def get_job_results(job_id: str) -> str:
        """Получает краткие результаты завершенной задачи.

        Args:
            job_id: ID задачи
        """
        from db.session import get_async_session
        from db import research_storage as rs

        async with get_async_session() as session:
            count = await rs.get_result_count(session, job_id)
            results = await rs.get_results(session, job_id, limit=5)

        if count == 0:
            return "Результатов пока нет. Задача может быть ещё в процессе."

        lines = [f"Найдено результатов: {count}. Первые 5:"]
        for r in results:
            title = r.title or r.source_url or "Без заголовка"
            lines.append(f"- {title[:80]}")
            if r.extracted_fields:
                for k, v in list(r.extracted_fields.items())[:3]:
                    lines.append(f"  {k}: {str(v)[:60]}")
        if count > 5:
            lines.append(f"\n...и ещё {count - 5}. Полный список в Research -> Jobs.")
        return "\n".join(lines)

    @tool
    async def cancel_research_job(job_id: str) -> str:
        """Отменяет задачу сбора данных.

        Args:
            job_id: ID задачи для отмены
        """
        result = await job_manager.cancel_job(user_id, job_id)
        if not result:
            return "Не удалось отменить задачу (не найдена или уже завершена)."
        return f"Задача {result['title']} отменена."

    return [
        create_research_job,
        run_research_job,
        check_job_status,
        list_research_jobs,
        get_job_results,
        cancel_research_job,
    ]
