## [00112ea] — 2026-03-18 21:52 (МСК)
📦 ProgressDashboard: фильтр активностей по типу + переименование «Рабочий вес»

## [76dcf60] — 2026-03-18 21:41 (МСК)
📦 ProgressDashboard: график активностей по неделям, кастомный dropdown, streak с активностями

## [9c4274a] — 2026-03-18 21:19 (МСК)
📦 AI Coach: данные активностей в промптах analyze_progress и get_recommendations

## [af2eb8b] — 2026-03-18 21:11 (МСК)
📦 Управление временем активностей/тренировок, интеграция ActivityLog в статистику, streak и AI Coach

## [e0abf66] — 2026-03-18 20:15 (МСК)
📦 Показ max 3 активностей на FitnessPage + кнопка Все/Свернуть

## [3b3cf9b] — 2026-03-18 19:57 (МСК)
📦 Отображение активностей (бег, шаги, вело и др.) в miniapp: GET /api/fitness/activities + карточки на FitnessPage

## [869e824] — 2026-03-17 19:20 (МСК)
📦 Фикс заголовков истории тренировок: авто-генерация имён из упражнений в finish_workout и quick_log_workout, MiniApp передаёт день программы при старте

## [3dab2c0] — 2026-03-17 19:10 (МСК)
📦 Фикс авто-создания шаблонов: update_program_day удаляет старый шаблон, coaching_template_apply требует подтверждения, fitness_agent спрашивает перед program_import

## [6e10488] — 2026-03-17 18:50 (МСК)
📦 Рефакторинг coaching модуля: два монолитных файла разбиты на 13 специализированных (API: schemas, goals, habits, checkins, analytics; Bot: onboarding, goals, habits, checkins, proactive, fsm + тонкие aggregator-файлы)

# 📦 GitHub — История версий бота

Лог всех изменений с хэшами коммитов для отката.

## [31aab4f] — 2026-03-16 17:53 (МСК)
📦 Фикс удаления шаблонов (FK constraint) и ложного грамм в классификаторе
- delete_all_templates: обнуление template_id в program_days перед удалением
- intent_classifier: " грамм " (пробелы с обеих сторон) в NUTRITION_STRONG

## [d38fad2] — 2026-03-16 17:38 (МСК)
📦 Фикс роутинга шаблонов в классификаторе + showConfirm в miniapp
- intent_classifier: шаблон тренир → FITNESS_STRONG, шаблон → FITNESS_NORMAL
- intent_classifier: фикс ложного грамм→программ (пробел перед грамм)
- ProgramsPage: window.confirm → Telegram.WebApp.showConfirm
- useTelegram: типы showConfirm/showAlert

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

## [563d5ed] — 2026-03-14 22:45 (МСК)
📦 Phase 7: 3-шаговый bot onboarding (профилирование), образовательные вставки в агент, re-engagement nudge, CoachPromptBubble в пустых состояниях Mini App
## [96b1731] — 2026-03-14 23:05\n📦 Phase 8: Adaptive Personalization — ежедневный анализ паттернов в scheduler, команда /reset_coach, API эндпоинты GET /coaching/profile/personalization и POST /coaching/profile/reset\n
## [a031042] — 2026-03-14 23:15\n📦 Phase 9: Cross-Module Intelligence — сбор сигналов из 5 модулей, 6 типов выводов, oркестрация действий с подтверждением, API и bot-хендлеры\n
## [96cdd51] — 2026-03-14 23:24\n📦 Phase 10: Analytics, Reliability, Polish — детальные метрики целей/привычек/вовлечённости, dropout risk с уровнями, auto weekly score, graceful degradation, structured logging\n

## [12c716b] — 2026-03-14 23:34 (МСК)
📦 Инфраструктура: health endpoint с DB-чеком, LLM таймаут 30s, обновлён /help, GitHub Actions CI/CD, оба сервиса переведены под systemd

## [c887897] — 2026-03-14 23:XX (МСК)
📦 Коучинг в миниапп: разблокирована кнопка навигации, исправлены все несоответствия полей между API и TypeScript-интерфейсами, miniapp пересобран и задеплоен
## [6cb9ad0] —  (МСК)
📦 Добавлен полный план тестирования Coaching модуля (docs/coaching_test_plan.md): 24 раздела, 300+ тест-кейсов, Test Pyramid, 5 персонажей, Factories/Fakes, Init/Unit/Integration/API/Chat/E2E/MiniApp тесты, Auth/Scheduler/CrossModule/Resilience, CI pipeline, Regression Pack, DoD, 6-фазный план
## [6cb9ad0] — 2026-03-14 23:57 (МСК)
📦 Добавлен полный план тестирования Coaching модуля (docs/coaching_test_plan.md): 24 раздела, 300+ тест-кейсов, Test Pyramid, 5 персонажей, Factories/Fakes, Init/Unit/Integration/API/Chat/E2E/MiniApp/Auth/Scheduler/CrossModule/Resilience, CI pipeline, Regression Pack R-001..R-010, DoD, 6-фазный план реализации
## [] — 
📦 Полное тест-покрытие Coaching модуля (Phase 1-6): 197 тестов, все зелёные. Исправлены баги в api/routers/coaching.py (priority тип, checkin mood/energy defaults, create_milestone маппинг, get_stuck_goals аргументы и др.)

## [e7fc18d] — 2026-03-15 01:51
📦 Добавлены полные FSM dialog тесты: goal creation (8+1 unit+E2E) и check-in (6+1 unit+E2E). Итого 205 тестов.

## [4e95102] — 2026-03-15 11:30
📦 Добавлены тесты proactive-подсказок (26 тестов) и mini-app journey сценариев (17 тестов); исправлены 3 продакшн-бага

## [0552622] — 2026-03-15 11:43 (МСК)
📦 Исправлены UI-баги mini-app: CoachPromptBubble получил насыщенный стиль, CheckInPage — исправлено несоответствие DTO с API (шкалы 1-5, mood→enum, reflection→notes)

## [34a0b32] — 2026-03-15 11:54 (МСК)
📦 Критические баги коучинга: session closed bug в coaching_main (бот не показывал кнопки), белый фон онбординга, перезапуск сервисов для сброса stale bytecode (.id ошибка)

## [e97348a] — 2026-03-15 12:02 (МСК)
📦 Редизайн CoachingDashboard: градиентный заголовок, сетка 2x2, empty state CTA-карточки для целей и привычек

## [9a3fced] — 2026-03-15 12:08 (МСК)
📦 vite.config: outDir=/var/www/jarvis — сборка теперь идёт прямо в nginx webroot, не нужно копировать вручную

## [9ac988f] — 2026-03-15 12:15 (МСК)
📦 Редизайн CoachingDashboard под тёмную тему приложения (GlassCard, CSS-vars); фикс NameError в coaching_handler (execute_orchestration_action)


## [4b88954] — 2026-03-15 12:36 (МСК)
📦 Редизайн всех страниц коучинга под тёмную тему: GoalCard, HabitCard, GoalsPage, GoalDetailPage, HabitsPage, WeeklyReviewPage, InsightsPage, CheckInPage, OnboardingPage — glass morphism, var(--app-text/hint/glass-bg), inline styles вместо Tailwind bg-*/text-*

## [2993739] — 2026-03-15 13:14 (МСК)
📦 Реализованы кнопки коучинга §9 архитектуры: кнопка «🎯 Коучинг» в главном меню, mood-labels в check-in, мотивационное меню, follow-up после выбора настроения, кнопки после создания цели и достижения, snooze для привычек, статус целей в review, контекстные состояния (overload/recovery/momentum)
## [40a9c93] — 2026-03-15 15:37 (МСК)
📦 Рефакторинг CoachingDashboard: приведение информационной иерархии в соответствие с §13.1 архитектуры (sticky State Card, горизонтальный strip привычек, Weekly Score секция, AI Insight после Goals, CoachPromptBubble только в пустых состояниях)

## [e7eb018] — 2026-03-15 15:52 (МСК)
📦 Рефакторинг CheckInPage: прогресс-индикатор, текстовые лейблы шкал, адаптивный вопрос коуча (§8.1), чипы быстрого действия (§9.3), примеры-чипы в полях (§11.3), голосовой ввод (SpeechRecognition), привязка к цели (§13.5), chat bridge

## [466135d] — 2026-03-15 16:02 (МСК)
📦 CheckInPage: расширенный режим по умолчанию, сохранение черновика в sessionStorage (восстанавливается при возврате), фикс VoiceMicButton (useRef вместо useCallback — stale closure)

## [98e8ff4] — 2026-03-15 16:19 (МСК)
📦 CheckInPage: вопрос коуча и чипы показываются сразу без ожидания первого тапа (убран moodTouched), добавлены key в AnimatePresence

## [e65d69c] — 2026-03-15 18:59 (МСК)
📦 fix: исправить POST /api/coaching/checkins — убрать несуществующее поле mood из GoalCheckin, автовыбор первой активной цели если goal_id=None


## [9e106ff] — 2026-03-15 19:46 (МСК)
📦 Добавлены проактивные дневные чекины (утро/день/вечер) с сохранением в БД: клавиатуры энергии и настроения, FSM вечерней рефлексии (4 шага), callback и FSM-обработчики, midday_pulse ритуал в планировщике

## [baf732f] — 2026-03-15 20:02 (МСК)
📦 Frontend: CheckInPage v3 — DayStrip 15 дней с цветными точками, SlotTabs (Утро/День/Вечер), read-only для заполненных слотов, разные формы по слотам, новые API-хуки useCheckInByDate/useCheckInCalendar
## [9743c44] — 2026-03-15 20:42 (МСК)
📦 Голосовые чекины через бота + страница инструкции в миниапп
## [7c0e89c] — 2026-03-15 20:52 (МСК)
📦 Исправления: скролл справки, маппинг mood, notes в утреннем чекине
## [9b5be25] — 2026-03-15 21:02 (МСК)
📦 Fix: кнопка Save перекрывалась BottomNav + скролл справки на десктопе
## [b7b2679] — 2026-03-15 21:20
📦 fix: убрать asyncio.gather с общим AsyncSession — 500 ошибка на /coaching/dashboard устранена, onboarding-экран на десктопе больше не показывается

## [cfb921d] — 2026-03-15 21:38
📦 fix: GoalsPage — FAB над BottomNav (zIndex:55), расширенная форма создания цели (area + why + first_step + deadline), CTA в пустом состоянии

## [c4ae628] — 2026-03-15 21:46
📦 fix: GoalCreateDto.priority — int→Optional[str], устраняет 500 при создании цели

## [f2d8e9e] — 2026-03-15 21:54
📦 fix: GoalCreateDto title min_length 2→1 (422 при однобуквенном названии цели)

## [96a155d] — 2026-03-15 (МСК)
📦 Исправлены 500 ошибки: dashboard (offset-naive/aware datetime) и checkins (check_date str->date)

## [db2eef1] — 2026-03-15 (МСК)
📦 Добавлена кнопка «Изменить» в SlotReadonly чекина — пре-заполнение формы + PATCH API

## [eaa79e6] — 2026-03-15 (МСК)
📦 Fix: форма редактирования чекина теперь открывается корректно (isFilled && !isEditMode)

## [6928746] — 2026-03-15 (МСК)
📦 Fix: после сохранения чекина остаёмся на странице (убран navigate)

## [1aa1cfe] — 2026-03-15 (МСК)
📦 Добавлена подпись «Справка» рядом с кнопкой ? в хедере CheckInPage


## [a384460] — 2026-03-15 22:59 (МСК)
📦 Модернизация чекина дня: DaySummaryCard (сводка при ≥2 слотах), кнопки настроения 🔥👍😐😔💀, фокус утра, привязка к цели + прогресс. CoachingDashboard: строка индикаторов ☀️⚡🌙 с тапом в нужный слот. Исправлен баг useEffect isEditMode.

## [59184b6] — 2026-03-15 23:04 (МСК)
📦 CoachingDashboard: кнопка «Добавить ещё цель» теперь отображается всегда (ранее исчезала при наличии хотя бы одной цели).

## [a35b2a1] — 2026-03-15 23:13 (МСК)
📦 Рефакторинг GoalsPage: убран поиск, stats-бар (активные/среднее/достигнуты), фильтры со счётчиками, hero-карточка пустого состояния, pill FAB «+ Новая цель», кнопка «Новая» в шапке. GoalCard: emoji области перед заголовком. Кнопка «Добавить ещё цель» в дашборде теперь открывает форму сразу через ?create=true.

## [9a56491] — 2026-03-15 23:15 (МСК)
📦 CoachingDashboard: убрана ссылка «📋 Инструкция по чекинам» с главного дашборда.

## [cf9efa3] — 2026-03-15 23:49 (МСК)
📦 GoalDetailPage: мета-блок, воронка этапов, привязанные привычки, bottom sheet прогресса, расширенная sticky-панель; бэкенд: goal_id в /habits; 3 новых хука; docs/goals-management.md

## [docs] — 2026-03-15 23:52 (МСК)
📦 docs/goals-management.md обновлена до v1.1: отражает реализованное состояние UI после cf9efa3

## [01be858] — 2026-03-15 23:59 (МСК)
🐛 fix: sticky domain больше не блокирует смену раздела; coaching-агент добавлен в роутинг supervisor

## [a2609e5] — 2026-03-16 00:14 (МСК)
🐛 fix: meal_type по текущему времени (инжект МСК); sticky domain сбрасывается при смене раздела (follow-up напоминаний)
## [0b3a350] — 2026-03-16 15:47 (МСК)
📦 Routing v3: L0a/L0b draft+confirmation guards в supervisor, Layer 1 авто-force в process_message, TTL sticky 3→8 мин, после clear_draft 5→10 мин; text.py — routing централизован в supervisor (исправлен баг: voice «Да.» при черновике еды → coaching)


## [] —  (С)
📦 икс фитнес-модуля: таймаут program_import 30→120с, coaching datetime, tool удаления шаблонов, UX кнопок программ

## [f1eb725] — 2026-03-16 17:06 (МСК)
📦 Фикс фитнес-модуля: таймаут program_import 30→120с, coaching datetime, tool удаления шаблонов, UX кнопок программ
## [d6397b3] — 2026-03-17 15:24 (МСК)
📦 Fix: синхронизация task.remind_at — напоминание из чата теперь видно в мини-аппе и не удаляется при редактировании задачи

## [19097f1] — 2026-03-17 15:39 (МСК)
📦 Fix: напоминания для повторяющихся задач — create_occurrence_reminders() в storage.py, автосоздание при регенерации, backfill при создании через чат

## [0d31872] — 2026-03-17 15:51 (МСК)
📦 Fix: Reminder-записи для фитнес-задач программы тренировок (fitness_storage обходил reminder_tools)


## [f549e68] — 2026-03-17 16:32 (МСК)
📦 fix(fitness): apply_template завершает сессию, фильтр зомби в get_next_workout, удалён дубль функции, проверка владельца в finish_session

## [] —  (МСК)
📦 Миграция бота и API в docker-compose: новые Dockerfile для bot/api, scheduler вынесен в отдельный контейнер (scheduler_main.py), добавлен сервис migrator для Alembic, Makefile обновлён на docker compose команды

## [3c944d2] — 2026-03-17 17:26 (МСК)
📦 Миграция бота и API в docker-compose: новые Dockerfile для bot/api, scheduler вынесен в отдельный контейнер (scheduler_main.py), добавлен сервис migrator для Alembic, Makefile обновлён на docker compose команды

## [5efb4d2] — 2026-03-17 17:44 (МСК)
🐛 fix(fitness): авто-сохранение подходов при завершении тренировки — история больше не сохраняется пустой
## [8588082] — 2026-03-17 17:51 (МСК)
📦 Исправлен баг: кнопка «Начать тренировку» в шаблонах теперь не создаёт сессию сразу — открывает ActiveWorkout с pre-loaded упражнениями, сессия создаётся при нажатии «Старт»

## [cf912ed] — 2026-03-17 17:56 (МСК)
📦 Security: CORS allow_origins=["*"] заменён на config.ALLOWED_ORIGINS — берётся из MINIAPP_URL в .env, wildcard убран

## [f6e838b] — 2026-03-17 18:18
📦 Убрано дублирование «приблизительно через X» в карточке задачи — относительное время дедлайна скрывается если интервал уже его показывает

## [21dac97] — 2026-03-17 18:21
📦 Полностью скрыт блок дедлайна (дата+время+relStr) в TaskCard когда уже есть intervalLabel — убрано дублирование «через X»

## [dc418d0] — 2026-03-17 18:35
📦 Напоминания для удалённых задач: scheduler тихо пропускает (вместо «задача не найдена»), delete_task отменяет pending-напоминания


## [cb553e9] — 2026-03-17 19:33 (МСК)
📦 Исправлены названия тренировок из шаблона и повтора: ActiveWorkout генерирует имя из списка упражнений до старта сессии; repeat_workout генерирует имя из упражнений если старое начиналось с «Тренировка »

## [61d3cb1] —  (МСК)
📦 Имя тренировки из шаблона теперь берётся напрямую из названия шаблона (например «Ноги + плечи»), а не генерируется из упражнений

## [61d3cb1] — 2026-03-17 19:42 (МСК)
📦 Имя тренировки из шаблона теперь берётся напрямую из названия шаблона (например «Ноги + плечи»), а не генерируется из упражнений

## [a6e5513] — 2026-03-17 19:53 (МСК)
📦 Убрана кнопка «Записать» из быстрых действий фитнес-страницы
## [9dc520f] — 2026-03-17 19:57
📦 AI Coach замена упражнения: группы мышц на русском (маппа MUSCLE_GROUP_RU), dropdown с непрозрачным фоном и z-50


## [7393386] — 2026-03-18 19:24 (МСК)
📦 Расширение фитнес-классификации: маркеры STRONG/NORMAL, sticky follow-up guard, промпт с 12 activity types (вариант B), emoji mapping, 50 тестов, документация

## [4d1d094] — 2026-03-18 22:01 (МСК)
📦 Адаптивная метрика в графике активностей: дистанция/время/шаги по типу

## [266eb1a] — 2026-03-18 22:06 (МСК)
📦 Показывать все упражнения в дропдауне прогресса (убран limit 5)

## [ab28441] — 2026-03-18 22:09 (МСК)
📦 Исключить кардио из дропдауна «Рабочий вес» (фильтр category != cardio)

## [14e21ca] — 2026-03-18 22:28 (МСК)
📦 Кнопки удаления/редактирования тренировок и активностей (главная + история)

## [06c8aff] — 2026-03-18 22:37 (МСК)
📦 Увеличены кнопки, убран повтор, добавлено редактирование тренировок (название/тип/заметки/настроение)

## [6f8ef4a] — 2026-03-18 22:50 (МСК)
📦 Редактирование подходов в тренировках: PATCH/DELETE /sets, форма с весом+повторы+добавление/удаление подходов

## [355374c] — 2026-03-18 23:05 (МСК)
📦 Перезапись EditSessionOverlay и EditSessionSheet — локальный стейт подходов, CSS Grid layout по паттерну QuickWorkoutSheet, батч-сохранение (add/update/delete) по кнопке


## [15c94e0] — 2026-03-18 23:09 (МСК)
📦 Sticky кнопка Сохранить — всегда видна внизу оверлея редактирования, с gradient-фейдом фона

