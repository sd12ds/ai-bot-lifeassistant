# 📦 GitHub — История версий бота

Лог всех изменений с хэшами коммитов для отката.

---

## [a437f79b3731ea430776af0886deed0a7f2730c5] — 2026-03-13
📦 Тест: проверка версионирования GitHub

## [304c975d76db698d4c47d8520d3e9ef0a417fbbc] — 2026-03-13
📦 Тест: откат тестового изменения

## [66a3e158bdbb679666582f22c1cd93fb6d72c2a4] — 2026-03-13
📦 Добавлена утилита форматирования даты

## [3dfdf3aca66eaa7e42c097bff4201d39f55e5217] — 2026-03-13
📦 Добавлены константы приложения

## [d9b4114a37595196b1e06f63409db889d956539d] — 2026-03-13
📦 Добавлен хелпер логирования

## [e104926f98bd04dc3898e313f847663e1b9e5e91] — 2026-03-13
📦 Добавлены утилиты: форматирование даты (format_date.py) и логирование (logger.py)

## [64a197b] — 2026-03-13 16:29 (МСК)
📦 Этап A: Nutrition Draft Engine — draft-based UX вместо FSM, merge engine (vision+caption), 5 новых draft tools, force_agent маршрутизация, Quick Actions кнопки

## [ce240a8] — 2026-03-13 17:05 (МСК)
📦 Этап C: интерактивность и удержание — Daily Score, Follow-up, Weekly Summary, клонирование приёмов, шаблоны, остаток КБЖУ, 3 API-эндпоинта

## [1d3096f] — 2026-03-13 17:10 (МСК)
📦 Исправлен .gitignore — добавлены все исходники db/, data/ и миграции в git

## [e9d34ba] — 2026-03-13 17:29 (МСК)
📦 Этап B+D: Reusable Chat-Core — универсальное ядро bot/core/ (BaseDraft, SessionContext, ActionResolver, DomainAdapter, FollowupEngine) + NutritionAdapter, рефакторинг nutrition_context в адаптер

## [da1eb73] — 2026-03-13 18:10 (МСК)
📦 Smart Routing v1: трёхуровневая маршрутизация (rule-based → sticky domain → LLM), обновление всех моделей на gpt-4.1-mini/nano, поддержка редактирования сохранённых приёмов через meal_reload_last, инжекция LAST_SAVED контекста

## [442c0f7] — 2026-03-13 18:16 (МСК)
📦 Бизнес-агенты (team, scheduler, crm) переведены на gpt-4.1-mini

## [969fdbf] — 2026-03-13 18:26 (МСК)
📦 Поддержка фото-альбомов: несколько фото → один объединённый draft (media group batching + debounce). Одиночные фото при активном draft дополняют его. Автоопределение типа приёма по времени суток.

## [cce5ebe] — 2026-03-13 19:15 (МСК)
📦 Импорт и редактирование программы тренировок через чат/голос. LLM-парсер текста, маппинг упражнений на справочник, 6 новых tools (import, show, replace, add, remove, swap). Документация: docs/workout-program-import.md

## [a7b1c51] — 2026-03-13 19:24 (МСК)
📦 Подсказки по функционалу в фитнес-агенте: контекстные hints после программ, силовых, кардио, замеров

## [b54491b] — 2026-03-13 19:34 (МСК)
📦 Добавлен program_delete tool — теперь бот может удалять программу тренировок через чат

## [4be80e0] — 2026-03-13 19:38 (МСК)
📦 fix: program_delete теперь деактивирует программу (is_active=False), а не удаляет из БД

## [5c363fb] — 2026-03-13 19:47 (МСК)
📦 fix: API DELETE /programs деактивирует (is_active=False) вместо удаления из БД. Miniapp: confirm-диалог перед деактивацией

## [06d8521] — 2026-03-13 19:56 (МСК)
📦 Настройка расписания программы через чат: program_set_schedule (день недели + время начала/окончания). Обновлены подсказки после импорта.

## [72151ba] — 2026-03-13 20:13 (МСК)
📦 Возврат реального удаления программ тренировок (chat tool + API). Проверка владельца сохранена. Confirm-диалог в miniapp оставлен.

## [abf84d5] — 2026-03-13 22:05 (МСК)
📦 Синхронизация программы тренировок с календарём: program_set_schedule и program_import автоматически создают workout-события. Валидация невалидного времени (24:xx).

## [7dfaee8] — 2026-03-13 23:08 (МСК)
📦 JWT авторизация для браузерного доступа: dual-auth (initData + Bearer JWT), команда /web для magic-link, страницы /auth и /auth-required.

## [9d59d4b] — 2026-03-13 23:26 (МСК)
📦 Документация: план действий для следующих сессий разработки (docs/next-session-plan.md)
## [58e5dc0] — 2026-03-14 20:30 (МСК)
📦 fix: Toast-уведомления для замеров тела — теперь показывает ошибку или успех при сохранении
## [4a84693] — 2026-03-14 20:39
📦 feat: прогресс по упражнениям — чипы топ-5 вместо dropdown/поиска

## [0d497f3] — 2026-03-14 21:36
📦 Фаза 1 Coaching: расширение goals/habits (9+9 полей), 17 новых coaching-таблиц, db/coaching_storage.py (49 методов), Alembic миграция dc98c42a69b6
## [09f692a] — 2026-03-14 21:50
📦 Phase 2 Coaching: 36 инструментов (coaching_tools.py), 5 контекстных tools (coaching_context_tools.py), coaching_agent.py с 8 режимами и динамическим context pack, supervisor routing, intent_classifier keywords


## [6084bb0] — 2026-03-14 22:07
📦 Phase 3 Coaching: coaching_handler.py (полный Aiogram router), регистрация в main.py, onboarding в /start, get_async_session в db/session.py

## [fc0f669] — 
📦 Phase 4 Coaching Proactive: 17 триггеров + 4 multi-signal + ритуалы (morning brief/evening/weekly/monthly/anti-dropout), antispam pipeline, coaching_scheduler.py

## [e1cff7b] — 2026-03-14 22:29 (МСК)
📦 Phase 5+6: FastAPI coaching router (40+ endpoints) + Mini App (9 экранов + 5 shared компонентов + роутинг)
