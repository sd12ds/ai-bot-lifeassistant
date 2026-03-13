"""
FastAPI приложение — REST API для Mini App и внешних клиентов.
Авторизация: Telegram initData через заголовок X-Init-Data.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import auth, tasks, calendars, nutrition, fitness, voice, ai_coach

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

# CORS — разрешаем запросы из Telegram Mini App (любой origin в dev, ограничить в prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Роутеры
app.include_router(auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(calendars.router, prefix="/api")

# Заглушки для будущих модулей — будут добавлены в следующих этапах
app.include_router(nutrition.router, prefix="/api")
app.include_router(fitness.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(ai_coach.router, prefix="/api")
# app.include_router(coaching.router, prefix="/api")
# app.include_router(crm.router, prefix="/api")
# app.include_router(team.router, prefix="/api")
# app.include_router(scheduler.router, prefix="/api")


@app.get("/api/health")
async def health():
    """Health-check endpoint."""
    return {"status": "ok"}
