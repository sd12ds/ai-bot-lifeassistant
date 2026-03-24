"""
FastAPI роутер для AI-чата.
SSE-стриминг ответов OpenAI с function calling для управления Research Platform.
"""
from __future__ import annotations

import json
import logging
import asyncio
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from openai import AsyncOpenAI

import config
from api.deps import get_current_user
from db.session import get_session
from db import research_storage as storage

logger = logging.getLogger("api.chat")

router = APIRouter(prefix="/research", tags=["chat"])

# OpenAI клиент
_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)

# Системный промпт
_SYSTEM_PROMPT = (
    "Ты — AI-ассистент платформы Research. Помогаешь пользователю управлять задачами исследований. "
    "Отвечай кратко и по делу на русском языке. "
    "Когда пользователь просит выполнить действие — используй доступные функции. "
    "Результаты функций форматируй в читаемый вид. "
    "Если пользователь задаёт общий вопрос — отвечай без вызова функций."
)

# Описание tools для OpenAI function calling
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_jobs",
            "description": "Получить список задач исследований пользователя. Можно фильтровать по статусу.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Фильтр по статусу: draft, running, completed, failed, canceled", "enum": ["draft", "running", "completed", "failed", "canceled"]},
                    "limit": {"type": "integer", "description": "Максимум задач (по умолч. 10)", "default": 10},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_job_details",
            "description": "Получить детали конкретной задачи по ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID задачи"},
                },
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_job",
            "description": "Создать новую задачу исследования.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Название задачи"},
                    "description": {"type": "string", "description": "Описание задачи"},
                    "job_type": {"type": "string", "description": "Тип задачи", "enum": ["search", "monitor", "scrape"], "default": "search"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_job",
            "description": "Запустить выполнение задачи.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID задачи для запуска"},
                },
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_job",
            "description": "Отменить выполняющуюся задачу.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID задачи для отмены"},
                },
                "required": ["job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Получить общую статистику: количество задач по статусам, общее число результатов.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_results",
            "description": "Получить результаты (найденные данные) конкретной задачи.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "ID задачи"},
                    "limit": {"type": "integer", "description": "Макс. кол-во результатов", "default": 20},
                },
                "required": ["job_id"],
            },
        },
    },
]


# Pydantic-схемы запроса
class ChatMessage(BaseModel):
    role: str  # user / assistant
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


# Выполнение tool calls
async def _execute_tool(name: str, args: dict, user_id: int, session: AsyncSession) -> str:
    """Выполнить вызов функции и вернуть JSON-строку с результатом."""
    try:
        if name == "list_jobs":
            # Получаем список задач пользователя
            jobs = await storage.list_jobs(session, user_id=user_id, status_filter=args.get("status"), limit=args.get("limit", 10))
            # Фильтрация по статусу уже передана в storage.list_jobs
            return json.dumps([
                {"id": j.id, "title": j.title, "status": j.status, "type": j.job_type,
                 "created": j.created_at.isoformat() if j.created_at else None}
                for j in jobs
            ], ensure_ascii=False)

        elif name == "get_job_details":
            # Детали конкретной задачи
            job = await storage.get_job(session, args["job_id"])
            if not job:
                return json.dumps({"error": "Задача не найдена"}, ensure_ascii=False)
            return json.dumps({
                "id": job.id, "title": job.title, "description": job.description,
                "status": job.status, "type": job.job_type, "provider": job.provider,
                "created": job.created_at.isoformat() if job.created_at else None,
                "last_run": job.last_run_at.isoformat() if job.last_run_at else None,
            }, ensure_ascii=False)

        elif name == "create_job":
            # Создание новой задачи через чат
            job = await storage.create_job(
                session, created_by=user_id, title=args["title"],
                job_type=args.get("job_type", "search"),
                description=args.get("description"), origin="chat",
            )
            await session.commit()
            return json.dumps({"id": job.id, "title": job.title, "status": job.status}, ensure_ascii=False)

        elif name == "run_job":
            # Запуск задачи в фоне (не блокируем стрим)
            from services.research.execution_engine import run_job as engine_run
            job = await storage.get_job(session, args["job_id"])
            if not job:
                return json.dumps({"error": "Задача не найдена"}, ensure_ascii=False)
            asyncio.create_task(engine_run(args["job_id"]))
            return json.dumps({"status": "started", "job_id": args["job_id"]}, ensure_ascii=False)

        elif name == "cancel_job":
            # Отмена задачи
            await storage.update_job_status(session, args["job_id"], "canceled")
            await session.commit()
            return json.dumps({"status": "canceled", "job_id": args["job_id"]}, ensure_ascii=False)

        elif name == "get_stats":
            # Статистика платформы для текущего пользователя
            from sqlalchemy import select, func
            from db.models import ResearchJob, ResearchResultItem
            stmt = select(ResearchJob.status, func.count()).where(
                ResearchJob.created_by == user_id
            ).group_by(ResearchJob.status)
            result = await session.execute(stmt)
            counts = dict(result.fetchall())
            res_stmt = (
                select(func.count()).select_from(ResearchResultItem)
                .join(ResearchJob, ResearchResultItem.job_id == ResearchJob.id)
                .where(ResearchJob.created_by == user_id)
            )
            total_results = (await session.execute(res_stmt)).scalar_one()
            return json.dumps({
                "total_jobs": sum(counts.values()), "running": counts.get("running", 0),
                "completed": counts.get("completed", 0), "failed": counts.get("failed", 0),
                "draft": counts.get("draft", 0), "total_results": total_results,
            }, ensure_ascii=False)

        elif name == "get_results":
            # Результаты конкретной задачи
            results = await storage.get_results(session, args["job_id"], limit=args.get("limit", 20))
            return json.dumps([
                {"id": r.id, "title": r.title, "url": r.source_url, "domain": r.domain}
                for r in results
            ], ensure_ascii=False)

        return json.dumps({"error": f"Неизвестная функция: {name}"}, ensure_ascii=False)

    except Exception as e:
        logger.exception("Tool execution error: %s", name)
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# SSE-стриминг endpoint
@router.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """AI-чат с SSE-стримингом. Поддерживает function calling для управления платформой."""

    # Собираем историю сообщений для OpenAI
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for msg in req.history[-20:]:  # ограничиваем контекст последними 20 сообщениями
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": req.message})

    async def _stream():
        """Генератор SSE-событий с поддержкой tool calls."""
        nonlocal messages
        try:
            while True:
                # Запрос к OpenAI со стримингом
                stream = await _client.chat.completions.create(
                    model=config.OPENAI_AGENT_MODEL,
                    messages=messages,
                    tools=_TOOLS,
                    stream=True,
                )

                # Аккумуляторы для стриминга
                collected_content = ""
                tool_calls_acc: dict[int, dict] = {}

                async for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    # Текстовый контент — отправляем SSE-токен сразу
                    if delta.content:
                        collected_content += delta.content
                        yield f"data: {json.dumps({'type': 'token', 'content': delta.content}, ensure_ascii=False)}\n\n"

                    # Tool calls — аккумулируем чанки
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                            if tc.id:
                                tool_calls_acc[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_acc[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += tc.function.arguments

                # Если нет tool calls — стрим завершён
                if not tool_calls_acc:
                    yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                    return

                # Есть tool calls — добавляем assistant message в историю
                assistant_msg = {"role": "assistant", "content": collected_content or None, "tool_calls": []}
                for idx in sorted(tool_calls_acc.keys()):
                    tc = tool_calls_acc[idx]
                    assistant_msg["tool_calls"].append({
                        "id": tc["id"], "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    })
                messages.append(assistant_msg)

                # Выполняем каждый tool call
                for idx in sorted(tool_calls_acc.keys()):
                    tc = tool_calls_acc[idx]
                    fn_name = tc["name"]
                    try:
                        fn_args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                    except json.JSONDecodeError:
                        fn_args = {}

                    # Уведомляем клиента о вызове функции
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': fn_name, 'args': fn_args}, ensure_ascii=False)}\n\n"

                    # Выполняем и добавляем результат в историю
                    result = await _execute_tool(fn_name, fn_args, user.telegram_id, session)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                # Цикл продолжается — OpenAI получит результаты tools

        except Exception as e:
            logger.exception("Chat stream error")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
