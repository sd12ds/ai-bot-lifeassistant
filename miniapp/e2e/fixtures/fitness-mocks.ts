/**
 * Мок-данные и хелперы для E2E тестов фитнес-модуля.
 * Перехватывает все /api/fitness/*, /api/ai/*, /api/voice/* запросы.
 */
import { Page } from "@playwright/test";

// ── Мок-данные ───────────────────────────────────────────────────────────────

/** Упражнения из справочника */
export const EXERCISES = [
  { id: 1, name: "Жим лёжа", category: "strength", muscle_group: "chest", equipment: "barbell", difficulty: "intermediate", is_compound: true, instructions: "", aliases: [] },
  { id: 2, name: "Жим стоя", category: "strength", muscle_group: "shoulders", equipment: "barbell", difficulty: "intermediate", is_compound: true, instructions: "", aliases: [] },
  { id: 3, name: "Приседания", category: "strength", muscle_group: "legs", equipment: "barbell", difficulty: "intermediate", is_compound: true, instructions: "", aliases: [] },
  { id: 4, name: "Подтягивания", category: "strength", muscle_group: "back", equipment: "bodyweight", difficulty: "intermediate", is_compound: true, instructions: "", aliases: [] },
  { id: 5, name: "Бег", category: "cardio", muscle_group: "legs", equipment: "none", difficulty: "beginner", is_compound: false, instructions: "", aliases: [] },
  { id: 6, name: "Велосипед", category: "cardio", muscle_group: "legs", equipment: "machine", difficulty: "beginner", is_compound: false, instructions: "", aliases: [] },
  { id: 7, name: "Растяжка", category: "flexibility", muscle_group: "full_body", equipment: "none", difficulty: "beginner", is_compound: false, instructions: "", aliases: [] },
  { id: 8, name: "Французский жим", category: "strength", muscle_group: "arms", equipment: "barbell", difficulty: "intermediate", is_compound: false, instructions: "", aliases: [] },
];

/** Дата сегодня в ISO */
const TODAY = new Date().toISOString();
const YESTERDAY = new Date(Date.now() - 86400000).toISOString();
const TWO_DAYS_AGO = new Date(Date.now() - 172800000).toISOString();

/** Подходы тренировки */
export const SAMPLE_SETS = [
  { id: 1, exercise_id: 1, set_num: 1, reps: 10, weight_kg: 80, duration_sec: null, distance_m: null, pace_sec_per_km: null, set_type: "working", is_personal_record: false },
  { id: 2, exercise_id: 1, set_num: 2, reps: 8, weight_kg: 85, duration_sec: null, distance_m: null, pace_sec_per_km: null, set_type: "working", is_personal_record: true },
  { id: 3, exercise_id: 1, set_num: 3, reps: 6, weight_kg: 90, duration_sec: null, distance_m: null, pace_sec_per_km: null, set_type: "working", is_personal_record: false },
  { id: 4, exercise_id: 3, set_num: 1, reps: 10, weight_kg: 100, duration_sec: null, distance_m: null, pace_sec_per_km: null, set_type: "working", is_personal_record: false },
  { id: 5, exercise_id: 3, set_num: 2, reps: 8, weight_kg: 110, duration_sec: null, distance_m: null, pace_sec_per_km: null, set_type: "working", is_personal_record: false },
];

/** Завершённые тренировки */
export const SESSIONS = [
  { id: 1, name: "Грудь + Трицепс", workout_type: "strength", started_at: YESTERDAY, ended_at: YESTERDAY, total_volume_kg: 2400, total_duration_sec: 3600, calories_burned: 350, mood_before: 4, mood_after: 5, notes: "", created_at: YESTERDAY, sets: SAMPLE_SETS.slice(0, 3) },
  { id: 2, name: "Ноги", workout_type: "strength", started_at: TWO_DAYS_AGO, ended_at: TWO_DAYS_AGO, total_volume_kg: 3200, total_duration_sec: 4200, calories_burned: 420, mood_before: 3, mood_after: 4, notes: "", created_at: TWO_DAYS_AGO, sets: SAMPLE_SETS.slice(3, 5) },
  { id: 3, name: "Кардио", workout_type: "cardio", started_at: TODAY, ended_at: TODAY, total_volume_kg: 0, total_duration_sec: 1800, calories_burned: 200, mood_before: 4, mood_after: 5, notes: "", created_at: TODAY, sets: [] },
];

/** Статистика */
export const STATS = {
  period_days: 30, total_sessions: 12, total_volume_kg: 28000,
  total_time_min: 720, total_calories: 4200, avg_mood: 4.2,
  top_exercises: [
    { exercise_id: 1, name: "Жим лёжа", sets_count: 36 },
    { exercise_id: 3, name: "Приседания", sets_count: 30 },
    { exercise_id: 4, name: "Подтягивания", sets_count: 24 },
  ],
  current_streak_days: 3,
};

/** Рекорды */
export const RECORDS = [
  { exercise: "Жим лёжа", record_type: "max_weight", value: 90, achieved_at: YESTERDAY },
  { exercise: "Приседания", record_type: "max_weight", value: 110, achieved_at: TWO_DAYS_AGO },
];

/** Замеры тела */
export const BODY_METRICS = [
  { id: 1, weight_kg: 82.5, body_fat_pct: null, muscle_mass_kg: null, chest_cm: 105, waist_cm: 82, hips_cm: 98, bicep_cm: 38, thigh_cm: null, energy_level: null, sleep_hours: null, recovery_rating: null, notes: "", logged_at: TODAY },
  { id: 2, weight_kg: 83.0, body_fat_pct: null, muscle_mass_kg: null, chest_cm: null, waist_cm: null, hips_cm: null, bicep_cm: null, thigh_cm: null, energy_level: null, sleep_hours: null, recovery_rating: null, notes: "", logged_at: YESTERDAY },
];

/** Фитнес-цель */
export const GOALS = {
  goal_type: "gain_muscle", workouts_per_week: 5, preferred_duration_min: 60,
  training_location: "gym", experience_level: "intermediate",
  available_equipment: [], target_weight_kg: 78,
};

/** Следующая тренировка из программы */
export const NEXT_WORKOUT = {
  program_name: "Набор массы 4×", day_number: 3, day_name: "День 3: Грудь + Трицепс",
  template_id: 1, total_days: 16, completed_workouts: 8,
};

/** Программы */
export const PROGRAMS = [
  { id: 1, user_id: 123, name: "Набор массы 4×", description: "4 дня в неделю", goal_type: "gain_muscle", duration_weeks: 4, days_per_week: 4, difficulty: "intermediate", location: "gym", is_active: true, created_at: TWO_DAYS_AGO, started_at: TWO_DAYS_AGO, days: [
    { id: 1, day_number: 1, day_name: "День 1: Грудь + Трицепс", template_id: 1 },
    { id: 2, day_number: 2, day_name: "День 2: Спина + Бицепс", template_id: 2 },
    { id: 3, day_number: 3, day_name: "День 3: Ноги", template_id: null },
    { id: 4, day_number: 4, day_name: "День 4: Плечи + Кор", template_id: null },
  ]},
];

/** Шаблоны */
export const TEMPLATES = [
  { id: 1, user_id: 123, name: "Грудь базовая", description: "Жим + разводка", created_at: TWO_DAYS_AGO, exercises: [
    { id: 1, exercise_id: 1, exercise_name: "Жим лёжа", exercise_category: "strength", sets: 4, reps: 8, weight_kg: 80, duration_sec: null, rest_sec: 90, sort_order: 1 },
    { id: 2, exercise_id: 8, exercise_name: "Французский жим", exercise_category: "strength", sets: 3, reps: 12, weight_kg: 30, duration_sec: null, rest_sec: 60, sort_order: 2 },
  ]},
];

/** Объём по неделям */
export const WEEKLY_VOLUME = [
  { week: "2026-02-24", sessions: 3, volume: 6800, duration_min: 180 },
  { week: "2026-03-03", sessions: 4, volume: 8200, duration_min: 240 },
  { week: "2026-03-10", sessions: 3, volume: 7100, duration_min: 195 },
];

/** Прогресс по упражнению */
export const EXERCISE_PROGRESS = [
  { date: "2026-02-25", max_weight: 75, volume: 2400, max_reps: 10 },
  { date: "2026-03-04", max_weight: 80, volume: 2720, max_reps: 10 },
  { date: "2026-03-11", max_weight: 85, volume: 2890, max_reps: 8 },
];

/** Еженедельная сводка */
export const WEEKLY_SUMMARY = {
  sessions: 3, sessions_goal: 5, sessions_prev: 4,
  volume_kg: 7100, volume_prev_kg: 8200, volume_change_pct: -13,
  time_min: 195, calories: 580, streak: 3, new_records: 1,
  records: [RECORDS[0]], top_exercises: STATS.top_exercises,
};

// ── Хелперы ──────────────────────────────────────────────────────────────────

/**
 * Перехватывает ВСЕ API-запросы фитнес-модуля и возвращает мок-данные.
 * Позволяет переопределять отдельные наборы данных.
 */
export async function mockFitnessApi(page: Page, overrides?: {
  sessions?: object[];
  stats?: object;
  exercises?: object[];
  bodyMetrics?: object[];
  goals?: object | null;
  programs?: object[];
  templates?: object[];
  records?: object[];
  nextWorkout?: object | null;
  weeklyVolume?: object[];
  exerciseProgress?: object[];
  weeklySummary?: object;
}) {
  const data = {
    sessions: overrides?.sessions ?? SESSIONS,
    stats: overrides?.stats ?? STATS,
    exercises: overrides?.exercises ?? EXERCISES,
    bodyMetrics: overrides?.bodyMetrics ?? BODY_METRICS,
    goals: overrides?.goals ?? GOALS,
    programs: overrides?.programs ?? PROGRAMS,
    templates: overrides?.templates ?? TEMPLATES,
    records: overrides?.records ?? RECORDS,
    nextWorkout: overrides?.nextWorkout ?? NEXT_WORKOUT,
    weeklyVolume: overrides?.weeklyVolume ?? WEEKLY_VOLUME,
    exerciseProgress: overrides?.exerciseProgress ?? EXERCISE_PROGRESS,
    weeklySummary: overrides?.weeklySummary ?? WEEKLY_SUMMARY,
  };

  // Перехватчик для фитнес-API
  await page.route("**/api/fitness/**", async (route) => {
    const url = route.request().url();
    const method = route.request().method();

    // GET /fitness/sessions
    if (method === "GET" && url.includes("/sessions") && !url.includes("/active") && !url.includes("/start")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.sessions) });
    }
    // GET /fitness/sessions/active
    if (method === "GET" && url.includes("/sessions/active")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(null) });
    }
    // POST /fitness/sessions/start
    if (method === "POST" && url.includes("/sessions/start")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: 999, name: "", workout_type: "strength", started_at: new Date().toISOString(), ended_at: null, total_volume_kg: 0, total_duration_sec: 0, calories_burned: 0, mood_before: null, mood_after: null, notes: "", created_at: new Date().toISOString(), sets: [] }) });
    }
    // POST /fitness/sessions/999/sets
    if (method === "POST" && url.match(/\/sessions\/\d+\/sets/)) {
      const body = JSON.parse(route.request().postData() || "{}");
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: Date.now(), exercise_id: body.exercise_id, set_num: 1, reps: body.reps || 10, weight_kg: body.weight_kg || 0, duration_sec: body.duration_sec || null, distance_m: null, pace_sec_per_km: null, set_type: body.set_type || "working", is_personal_record: false }) });
    }
    // PUT /fitness/sessions/999/finish
    if (method === "PUT" && url.match(/\/sessions\/\d+\/finish/)) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...data.sessions[0], id: 999, ended_at: new Date().toISOString() }) });
    }
    // GET /fitness/exercises/search
    if (method === "GET" && url.includes("/exercises/search")) {
      const urlObj = new URL(url);
      const q = (urlObj.searchParams.get("q") || "").toLowerCase();
      const category = urlObj.searchParams.get("category");
      const muscleGroup = urlObj.searchParams.get("muscle_group");
      let filtered = data.exercises as any[];
      if (q) filtered = filtered.filter((e: any) => e.name.toLowerCase().includes(q));
      if (category) filtered = filtered.filter((e: any) => e.category === category);
      if (muscleGroup) filtered = filtered.filter((e: any) => e.muscle_group === muscleGroup);
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(filtered) });
    }
    // GET /fitness/exercises/:id
    if (method === "GET" && url.match(/\/exercises\/\d+$/)) {
      const id = parseInt(url.split("/").pop()!);
      const ex = (data.exercises as any[]).find((e: any) => e.id === id);
      return route.fulfill({ status: ex ? 200 : 404, contentType: "application/json", body: JSON.stringify(ex || { detail: "Not found" }) });
    }
    // GET /fitness/stats
    if (method === "GET" && url.includes("/stats")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.stats) });
    }
    // GET /fitness/records
    if (method === "GET" && url.includes("/records")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.records) });
    }
    // GET /fitness/goals
    if (method === "GET" && url.includes("/goals")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.goals) });
    }
    // PUT /fitness/goals
    if (method === "PUT" && url.includes("/goals")) {
      const body = JSON.parse(route.request().postData() || "{}");
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...data.goals, ...body }) });
    }
    // GET /fitness/body-metrics
    if (method === "GET" && url.includes("/body-metrics") && !url.includes("/photos")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.bodyMetrics) });
    }
    // POST /fitness/body-metrics
    if (method === "POST" && url.includes("/body-metrics") && !url.includes("/photos")) {
      const body = JSON.parse(route.request().postData() || "{}");
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: Date.now(), ...body, logged_at: new Date().toISOString() }) });
    }
    // GET /fitness/body-metrics/photos
    if (method === "GET" && url.includes("/body-metrics/photos")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
    }
    // GET /fitness/programs
    if (method === "GET" && url.includes("/programs") && !url.includes("/active") && !url.includes("/next-workout")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.programs) });
    }
    // GET /fitness/programs/active
    if (method === "GET" && url.includes("/programs/active")) {
      const active = (data.programs as any[]).find((p: any) => p.is_active) || null;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(active) });
    }
    // GET /fitness/programs/next-workout
    if (method === "GET" && url.includes("/next-workout")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.nextWorkout) });
    }
    // POST /fitness/programs/generate
    if (method === "POST" && url.includes("/programs/generate")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...data.programs[0], id: Date.now(), name: "AI-программа" }) });
    }
    // PUT /fitness/programs/:id/activate
    if (method === "PUT" && url.includes("/activate")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ...(data.programs[0] as any), is_active: true }) });
    }
    // DELETE /fitness/programs/:id
    if (method === "DELETE" && url.includes("/programs/")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    }
    // GET /fitness/templates
    if (method === "GET" && url.includes("/templates")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.templates) });
    }
    // DELETE /fitness/templates/:id
    if (method === "DELETE" && url.includes("/templates/")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    }
    // GET /fitness/weekly-volume
    if (method === "GET" && url.includes("/weekly-volume")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.weeklyVolume) });
    }
    // GET /fitness/exercises/:id/progress
    if (method === "GET" && url.includes("/progress")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.exerciseProgress) });
    }
    // GET /fitness/insights/weekly
    if (method === "GET" && url.includes("/insights/weekly")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(data.weeklySummary) });
    }
    // Остальное — пропускаем
    return route.continue();
  });

  // Перехватчик для AI-эндпоинтов
  await page.route("**/api/ai/**", async (route) => {
    const url = route.request().url();
    if (url.includes("/build-workout")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ name: "AI Тренировка: Грудь", description: "Тренировка на грудь для среднего уровня", exercises: [{ exercise_id: 1, exercise_name: "Жим лёжа", sets: 4, reps: 8, rest_sec: 90, notes: "Контролируй негативную фазу" }] }) });
    }
    if (url.includes("/replace-exercise")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ original: "Жим лёжа", alternatives: [{ exercise_id: 2, exercise_name: "Жим стоя", reason: "Нагружает передний пучок дельт" }, { exercise_id: 8, exercise_name: "Французский жим", reason: "Изолирует трицепс" }] }) });
    }
    if (url.includes("/analyze-progress")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ analysis: "За последние 30 дней вы провели 12 тренировок. Объём растёт.", highlights: ["Рост рабочего веса на 5 кг", "Streak 3 дня"], trend: "improving" }) });
    }
    if (url.includes("/recommendations")) {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ recommendations: [{ icon: "💪", title: "Увеличь объём ног", text: "Ноги отстают — добавь ещё 1 день ног" }], weekly_focus: "Сфокусируйся на нижней части тела" }) });
    }
    return route.continue();
  });

  // Перехватчик для задач и других API (чтобы не падали)
  await page.route("**/api/tasks/**", async (route) => {
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/api/nutrition/**", async (route) => {
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/api/calendar/**", async (route) => {
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
}
