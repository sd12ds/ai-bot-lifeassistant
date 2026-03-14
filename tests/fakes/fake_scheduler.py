"""
Заглушка APScheduler для тестирования планировщика.
"""
from __future__ import annotations

from typing import Any, Callable


class FakeScheduler:
    """
    Имитирует APScheduler для тестирования без реального планировщика.
    Записывает добавленные и удалённые задания.
    """

    def __init__(self) -> None:
        # Словарь зарегистрированных заданий {job_id: job_info}
        self.jobs: dict[str, dict] = {}
        # Флаг запущенного планировщика
        self.running: bool = False

    def add_job(
        self,
        func: Callable,
        trigger: str = "interval",
        id: str | None = None,
        **kwargs: Any,
    ) -> dict:
        """Регистрирует задание без реального выполнения."""
        job_id = id or f"job_{len(self.jobs)}"
        job_info = {
            "id": job_id,
            "func": func,
            "trigger": trigger,
            **kwargs,
        }
        self.jobs[job_id] = job_info
        return job_info

    def remove_job(self, job_id: str) -> None:
        """Удаляет задание."""
        self.jobs.pop(job_id, None)

    def get_jobs(self) -> list[dict]:
        """Возвращает список всех заданий."""
        return list(self.jobs.values())

    def start(self) -> None:
        """Имитирует запуск планировщика."""
        self.running = True

    def shutdown(self, wait: bool = True) -> None:
        """Имитирует остановку планировщика."""
        self.running = False

    def has_job(self, job_id: str) -> bool:
        """Проверяет, зарегистрировано ли задание."""
        return job_id in self.jobs

    def reset(self) -> None:
        """Очищает все зарегистрированные задания."""
        self.jobs = {}
        self.running = False
