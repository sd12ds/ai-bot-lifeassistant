"""
FastAPI приложение — REST API для Mini App и внешних клиентов.
Авторизация: Telegram initData через заголовок X-Init-Data.
"""
import time as _time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from api.routers import auth, tasks, calendars, nutrition, fitness, voice, ai_coach, coaching, research, workspace, billing

# Время старта приложения — используется в /api/health для расчёта uptime
_START_TIME = _time.time()

# ── Приложение ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Personal & Business Assistant API",
    description="REST API для Telegram Mini App",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    # Отключаем автоматический редирект /api/tasks → /api/tasks/
    # Без этого браузер теряет X-Init-Data заголовок при редиректе → 401
    redirect_slashes=False,
)

# CORS — origin'ы берутся из config.ALLOWED_ORIGINS (ALLOWED_ORIGINS или MINIAPP_URL в .env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,  # задаётся через ALLOWED_ORIGINS или MINIAPP_URL в .env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Роутеры
app.include_router(auth.router, prefix="/api")
app.include_router(research.router, prefix="/api")
app.include_router(workspace.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(calendars.router, prefix="/api")

# Подключённые модули
app.include_router(nutrition.router, prefix="/api")
app.include_router(fitness.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(ai_coach.router, prefix="/api")
app.include_router(coaching.router, prefix="/api")  # Coaching модуль (Phase 1-10)
# app.include_router(crm.router, prefix="/api")
# app.include_router(team.router, prefix="/api")
# app.include_router(scheduler.router, prefix="/api")


@app.get("/api/health")
async def health():
    """Health-check endpoint — проверяет статус API и подключение к БД."""
    from sqlalchemy import text
    from db.session import get_async_session

    # Вычисляем время работы приложения в секундах
    uptime = int(_time.time() - _START_TIME)
    db_status = "ok"

    # Проверяем соединение с PostgreSQL простым запросом SELECT 1
    try:
        async with get_async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"error: {exc}"

    # Общий статус: ok если всё работает, degraded если БД недоступна
    overall = "ok" if db_status == "ok" else "degraded"
    return {"status": overall, "db": db_status, "uptime_seconds": uptime}
