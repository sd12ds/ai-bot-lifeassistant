/**
 * API-слой фитнес-модуля: типы, запросы, React Query хуки.
 * Все запросы через apiClient с авторизацией X-Init-Data.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

// ── Типы ──────────────────────────────────────────────────────────────────────

/** Упражнение из справочника */
export interface Exercise {
  id: number
  name: string
  category: string | null
  muscle_group: string | null
  equipment: string | null
  difficulty: string
  is_compound: boolean
  instructions: string
  aliases: string[]
}

/** Данные подхода */
export interface SetData {
  reps?: number | null
  weight_kg?: number | null
  duration_sec?: number | null
  distance_m?: number | null
  pace_sec_per_km?: number | null
  set_type?: string
}

/** Подход (ответ) */
export interface WorkoutSet {
  id: number
  exercise_id: number
  exercise_name: string | null  // название упражнения из справочника
  set_num: number | null
  reps: number | null
  weight_kg: number | null
  duration_sec: number | null
  distance_m: number | null
  pace_sec_per_km: number | null
  set_type: string
  is_personal_record: boolean
}

/** Тренировка */
export interface WorkoutSession {
  id: number
  name: string | null
  workout_type: string
  started_at: string | null
  ended_at: string | null
  total_volume_kg: number | null
  total_duration_sec: number | null
  calories_burned: number | null
  mood_before: number | null
  mood_after: number | null
  notes: string
  created_at: string | null
  sets: WorkoutSet[]
}

/** DTO создания тренировки */
export interface WorkoutCreateDto {
  name?: string
  workout_type?: string
  exercises: {
    exercise_id: number
    sets: SetData[]
  }[]
}

/** Замер тела */
export interface BodyMetric {
  id: number
  weight_kg: number | null
  body_fat_pct: number | null
  muscle_mass_kg: number | null
  chest_cm: number | null
  waist_cm: number | null
  hips_cm: number | null
  bicep_cm: number | null
  thigh_cm: number | null
  energy_level: number | null
  sleep_hours: number | null
  recovery_rating: number | null
  notes: string
  logged_at: string | null
}

/** DTO записи замеров */
export interface BodyMetricCreateDto {
  weight_kg?: number | null
  body_fat_pct?: number | null
  chest_cm?: number | null
  waist_cm?: number | null
  hips_cm?: number | null
  bicep_cm?: number | null
  thigh_cm?: number | null
  energy_level?: number | null
  sleep_hours?: number | null
  recovery_rating?: number | null
  notes?: string
}

/** Статистика тренировок */
export interface FitnessStats {
  period_days: number
  total_sessions: number
  total_volume_kg: number
  total_time_min: number
  total_calories: number
  avg_mood: number | null
  top_exercises: { exercise_id: number; name: string; sets_count: number }[]
  current_streak_days: number
}

/** Личный рекорд */
export interface PersonalRecord {
  exercise: string
  record_type: string
  value: number
  achieved_at: string | null
}

/** Фитнес-цель */
export interface FitnessGoal {
  goal_type: string
  workouts_per_week: number
  preferred_duration_min: number
  training_location: string
  experience_level: string
  available_equipment: string[]
  target_weight_kg?: number | null
}


/** Фото прогресса */
export interface ProgressPhoto {
  id: number
  filename: string
  url: string
  logged_at: string | null
  weight_kg: number | null
  notes: string
}

// ── API-функции ───────────────────────────────────────────────────────────────

/** Поиск упражнений */
const searchExercisesApi = async (q: string, category?: string, muscleGroup?: string): Promise<Exercise[]> =>
  (await apiClient.get('/fitness/exercises/search', {
    params: { q, category: category || undefined, muscle_group: muscleGroup || undefined },
  })).data

/** Детали упражнения */
const fetchExercise = async (id: number): Promise<Exercise> =>
  (await apiClient.get(`/fitness/exercises/${id}`)).data

/** Создать/залогировать тренировку */
const createSession = async (dto: WorkoutCreateDto): Promise<WorkoutSession> =>
  (await apiClient.post('/fitness/sessions', dto)).data

/** Список тренировок */
const fetchSessions = async (days: number = 7, limit: number = 20): Promise<WorkoutSession[]> =>
  (await apiClient.get('/fitness/sessions', { params: { days, limit } })).data

/** Активная тренировка */
const fetchActiveSession = async (): Promise<WorkoutSession | null> =>
  (await apiClient.get('/fitness/sessions/active')).data

/** Повторить тренировку */
const repeatSessionApi = async (sessionId: number): Promise<WorkoutSession> =>
  (await apiClient.post(`/fitness/sessions/${sessionId}/repeat`)).data

/** Записать замер тела */
const createBodyMetric = async (dto: BodyMetricCreateDto): Promise<BodyMetric> =>
  (await apiClient.post('/fitness/body-metrics', dto)).data

/** История замеров */
const fetchBodyMetrics = async (days: number = 30, limit: number = 20): Promise<BodyMetric[]> =>
  (await apiClient.get('/fitness/body-metrics', { params: { days, limit } })).data

/** Статистика */
const fetchStats = async (days: number = 30): Promise<FitnessStats> =>
  (await apiClient.get('/fitness/stats', { params: { days } })).data

/** Личные рекорды */
const fetchRecords = async (): Promise<PersonalRecord[]> =>
  (await apiClient.get('/fitness/records')).data

/** Фитнес-цель */
const fetchGoals = async (): Promise<FitnessGoal | null> =>
  (await apiClient.get('/fitness/goals')).data

/** Обновить фитнес-цель */
const updateGoalsApi = async (dto: Partial<FitnessGoal>): Promise<FitnessGoal> =>
  (await apiClient.put('/fitness/goals', dto)).data


/** Загрузить фото прогресса */
const uploadPhotoApi = async (file: File, notes?: string): Promise<ProgressPhoto> => {
  // Формируем FormData для multipart загрузки
  const formData = new FormData()
  formData.append('file', file)
  if (notes) formData.append('notes', notes)
  return (await apiClient.post('/fitness/body-metrics/photos', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })).data
}

/** Список фото прогресса */
const fetchPhotosApi = async (): Promise<ProgressPhoto[]> =>
  (await apiClient.get('/fitness/body-metrics/photos')).data

/** Удалить фото прогресса */
const deletePhotoApi = async (photoId: number): Promise<void> =>
  (await apiClient.delete(`/fitness/body-metrics/photos/${photoId}`)).data

// ── React Query хуки ──────────────────────────────────────────────────────────

/** Поиск упражнений (с debounce) */
export function useExerciseSearch(query: string, category?: string, muscleGroup?: string) {
  return useQuery({
    queryKey: ['fitness', 'exercises', 'search', query, category, muscleGroup],
    queryFn: () => searchExercisesApi(query, category, muscleGroup),
    enabled: query.length >= 2 || !!category || !!muscleGroup,
    staleTime: 30_000,
  })
}

/** Детали упражнения */
export function useExercise(id: number) {
  return useQuery({
    queryKey: ['fitness', 'exercises', id],
    queryFn: () => fetchExercise(id),
    enabled: id > 0,
  })
}

/** Список тренировок */
export function useSessions(days: number = 7) {
  return useQuery({
    queryKey: ['fitness', 'sessions', days],
    queryFn: () => fetchSessions(days),
  })
}

/** Активная тренировка */
export function useActiveSession() {
  return useQuery({
    queryKey: ['fitness', 'sessions', 'active'],
    queryFn: fetchActiveSession,
  })
}

/** Создать тренировку */
export function useCreateSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createSession,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fitness'] })
    },
  })
}

/** Повторить тренировку */
export function useRepeatSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: repeatSessionApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fitness'] })
    },
  })
}

/** Записать замер тела */
export function useCreateBodyMetric() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createBodyMetric,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fitness', 'body-metrics'] })
    },
  })
}

/** История замеров */
export function useBodyMetrics(days: number = 30) {
  return useQuery({
    queryKey: ['fitness', 'body-metrics', days],
    queryFn: () => fetchBodyMetrics(days),
  })
}

/** Статистика */
export function useFitnessStats(days: number = 30) {
  return useQuery({
    queryKey: ['fitness', 'stats', days],
    queryFn: () => fetchStats(days),
  })
}

/** Личные рекорды */
export function useRecords() {
  return useQuery({
    queryKey: ['fitness', 'records'],
    queryFn: fetchRecords,
  })
}

/** Фитнес-цель */
export function useFitnessGoals() {
  return useQuery({
    queryKey: ['fitness', 'goals'],
    queryFn: fetchGoals,
  })
}

/** Обновить фитнес-цель */
export function useUpdateFitnessGoals() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateGoalsApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fitness', 'goals'] })
    },
  })
}


/** Список фото прогресса */
export function useProgressPhotos() {
  return useQuery({
    queryKey: ['fitness', 'body-metrics', 'photos'],
    queryFn: fetchPhotosApi,
  })
}

/** Загрузить фото прогресса */
export function useUploadPhoto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ file, notes }: { file: File; notes?: string }) => uploadPhotoApi(file, notes),
    onSuccess: () => {
      // Инвалидируем фото и замеры
      qc.invalidateQueries({ queryKey: ['fitness', 'body-metrics'] })
    },
  })
}

/** Удалить фото прогресса */
export function useDeletePhoto() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deletePhotoApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fitness', 'body-metrics'] })
    },
  })
}

// ── Типы для Sprint 3 ────────────────────────────────────────────────────────

/** Прогресс по упражнению — точка на графике */
export interface ExerciseProgressPoint {
  date: string
  max_weight: number
  volume: number
  max_reps: number
}

/** Объём за неделю — для столбчатого графика */
export interface WeeklyVolumePoint {
  week: string
  sessions: number
  volume: number
  duration_min: number
}

/** DTO начала тренировки */
export interface SessionStartDto {
  name?: string
  workout_type?: string
  mood_before?: number | null
}

/** DTO добавления подхода */
export interface AddSetDto {
  exercise_id: number
  reps?: number | null
  weight_kg?: number | null
  duration_sec?: number | null
  distance_m?: number | null
  set_type?: string
}

/** DTO завершения тренировки */
export interface FinishSessionDto {
  mood_after?: number | null
  notes?: string
}

// ── API-функции Sprint 3 ─────────────────────────────────────────────────────

/** Начать активную тренировку */
const startSessionApi = async (dto: SessionStartDto): Promise<WorkoutSession> =>
  (await apiClient.post('/fitness/sessions/start', dto)).data

/** Добавить подход к активной тренировке */
const addSetApi = async ({ sessionId, dto }: { sessionId: number; dto: AddSetDto }): Promise<WorkoutSet> =>
  (await apiClient.post(`/fitness/sessions/${sessionId}/sets`, dto)).data

/** Завершить тренировку */
const finishSessionApi = async ({ sessionId, dto }: { sessionId: number; dto: FinishSessionDto }): Promise<WorkoutSession> =>
  (await apiClient.put(`/fitness/sessions/${sessionId}/finish`, dto)).data

/** Прогресс по упражнению */
const fetchExerciseProgress = async (exerciseId: number, days: number = 90): Promise<ExerciseProgressPoint[]> =>
  (await apiClient.get(`/fitness/exercises/${exerciseId}/progress`, { params: { days } })).data

/** Объём по неделям */
const fetchWeeklyVolume = async (weeks: number = 8): Promise<WeeklyVolumePoint[]> =>
  (await apiClient.get('/fitness/weekly-volume', { params: { weeks } })).data

// ── React Query хуки Sprint 3 ────────────────────────────────────────────────

/** Начать тренировку */
export function useStartSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: startSessionApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fitness', 'sessions'] })
    },
  })
}

/** Добавить подход */
export function useAddSet() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: addSetApi,
    onSuccess: () => {
      // Инвалидируем активную сессию для обновления данных
      qc.invalidateQueries({ queryKey: ['fitness', 'sessions', 'active'] })
    },
  })
}

/** Завершить тренировку */
export function useFinishSession() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: finishSessionApi,
    onSuccess: () => {
      // Инвалидируем все фитнес-данные после завершения
      qc.invalidateQueries({ queryKey: ['fitness'] })
    },
  })
}

/** Прогресс по упражнению */
export function useExerciseProgress(exerciseId: number, days: number = 90) {
  return useQuery({
    queryKey: ['fitness', 'exercises', exerciseId, 'progress', days],
    queryFn: () => fetchExerciseProgress(exerciseId, days),
    enabled: exerciseId > 0,
  })
}

/** Объём по неделям */
export function useWeeklyVolume(weeks: number = 8) {
  return useQuery({
    queryKey: ['fitness', 'weekly-volume', weeks],
    queryFn: () => fetchWeeklyVolume(weeks),
  })
}

// ── Типы Sprint 4: Программы, Шаблоны, Insights ─────────────────────────────

/** День программы */
export interface ProgramDay {
  id: number
  day_number: number
  day_name: string | null
  template_id: number | null
  weekday: number | null
  weekday_name: string | null
  preferred_start_time: string | null
  preferred_end_time: string | null
}

/** Программа тренировок */
export interface Program {
  id: number
  user_id: number
  name: string
  description: string
  goal_type: string | null
  duration_weeks: number | null
  days_per_week: number
  difficulty: string
  location: string
  is_active: boolean
  created_at: string | null
  started_at: string | null
  days: ProgramDay[]
}

/** DTO генерации программы */
export interface ProgramGenerateDto {
  goal_type?: string
  difficulty?: string
  location?: string
  days_per_week?: number
  duration_weeks?: number
  equipment?: string[]
  notes?: string
}

/** Следующая тренировка */
export interface NextWorkout {
  program_name: string
  day_number: number
  day_name: string | null
  weekday: number | null
  weekday_name: string | null
  template_id: number | null
  total_days: number
  completed_workouts: number
  is_today: boolean
}

/** Упражнение шаблона */
export interface TemplateExercise {
  id: number
  exercise_id: number
  exercise_name: string       // Название упражнения из справочника
  exercise_category: string   // Категория (strength/cardio/flexibility)
  sets: number
  reps: number | null
  weight_kg: number | null
  duration_sec: number | null
  rest_sec: number
  sort_order: number
}

/** Шаблон */
export interface Template {
  id: number
  user_id: number
  name: string
  description: string
  created_at: string | null
  exercises: TemplateExercise[]
}

/** Советы после тренировки */
export interface PostWorkoutTips {
  tips: string[]
}

/** Еженедельная сводка */
export interface WeeklySummary {
  sessions: number
  sessions_goal: number
  sessions_prev: number
  volume_kg: number
  volume_prev_kg: number
  volume_change_pct: number
  time_min: number
  calories: number
  streak: number
  new_records: number
  records: any[]
  top_exercises: any[]
}

// ── API-функции Sprint 4 ─────────────────────────────────────────────────────

/** Список программ */
const fetchPrograms = async (): Promise<Program[]> =>
  (await apiClient.get('/fitness/programs')).data

/** Активная программа */
const fetchActiveProgram = async (): Promise<Program | null> =>
  (await apiClient.get('/fitness/programs/active')).data

/** Создать программу */
const createProgramApi = async (dto: any): Promise<Program> =>
  (await apiClient.post('/fitness/programs', dto)).data

/** AI-генерация программы */
const generateProgramApi = async (dto: ProgramGenerateDto): Promise<Program> =>
  (await apiClient.post('/fitness/programs/generate', dto)).data

/** Активировать программу */
const activateProgramApi = async (id: number): Promise<Program> =>
  (await apiClient.put(`/fitness/programs/${id}/activate`)).data

/** Удалить программу */
const deleteProgramApi = async (id: number): Promise<void> =>
  (await apiClient.delete(`/fitness/programs/${id}`)).data

/** Следующая тренировка */
const fetchNextWorkout = async (): Promise<NextWorkout | null> =>
  (await apiClient.get('/fitness/programs/next-workout')).data

/** Список шаблонов */
const fetchTemplates = async (): Promise<Template[]> =>
  (await apiClient.get('/fitness/templates')).data

/** Создать шаблон */
const createTemplateApi = async (dto: any): Promise<Template> =>
  (await apiClient.post('/fitness/templates', dto)).data

/** Применить шаблон */
const applyTemplateApi = async (id: number): Promise<WorkoutSession> =>
  (await apiClient.post(`/fitness/templates/${id}/apply`)).data

/** Удалить шаблон */
const deleteTemplateApi = async (id: number): Promise<void> =>
  (await apiClient.delete(`/fitness/templates/${id}`)).data

/** Советы после тренировки */
const fetchPostWorkoutTips = async (sessionId: number): Promise<PostWorkoutTips> =>
  (await apiClient.get(`/fitness/insights/post-workout/${sessionId}`)).data

/** Еженедельная сводка */
const fetchWeeklySummary = async (): Promise<WeeklySummary> =>
  (await apiClient.get('/fitness/insights/weekly')).data

// ── React Query хуки Sprint 4 ────────────────────────────────────────────────

/** Список программ */
export function usePrograms() {
  return useQuery({
    queryKey: ['fitness', 'programs'],
    queryFn: fetchPrograms,
  })
}

/** Активная программа */
export function useActiveProgram() {
  return useQuery({
    queryKey: ['fitness', 'programs', 'active'],
    queryFn: fetchActiveProgram,
  })
}

/** Создать программу */
export function useCreateProgram() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createProgramApi,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fitness', 'programs'] }) },
  })
}

/** AI-генерация программы */
export function useGenerateProgram() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: generateProgramApi,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fitness', 'programs'] }) },
  })
}

/** Активировать программу */
export function useActivateProgram() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: activateProgramApi,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fitness', 'programs'] }) },
  })
}

/** Удалить программу */
export function useDeleteProgram() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteProgramApi,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fitness', 'programs'] }) },
  })
}

/** Следующая тренировка */
export function useNextWorkout() {
  return useQuery({
    queryKey: ['fitness', 'programs', 'next-workout'],
    queryFn: fetchNextWorkout,
  })
}

/** Список шаблонов */
export function useTemplates() {
  return useQuery({
    queryKey: ['fitness', 'templates'],
    queryFn: fetchTemplates,
  })
}

/** Создать шаблон */
export function useCreateTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createTemplateApi,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fitness', 'templates'] }) },
  })
}

/** Применить шаблон */
export function useApplyTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: applyTemplateApi,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fitness'] }) },
  })
}

/** Удалить шаблон */
export function useDeleteTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteTemplateApi,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['fitness', 'templates'] }) },
  })
}

/** Советы после тренировки */
export function usePostWorkoutTips(sessionId: number) {
  return useQuery({
    queryKey: ['fitness', 'insights', 'post-workout', sessionId],
    queryFn: () => fetchPostWorkoutTips(sessionId),
    enabled: sessionId > 0,
  })
}

/** Еженедельная сводка */
export function useWeeklySummary() {
  return useQuery({
    queryKey: ['fitness', 'insights', 'weekly'],
    queryFn: fetchWeeklySummary,
  })
}

// ── Типы Sprint 5C: AI Coach ─────────────────────────────────────────────────

/** DTO для AI-сборки тренировки */
export interface AiBuildWorkoutDto {
  muscle_groups: string[]
  duration_min?: number
  location?: string
  difficulty?: string
  notes?: string
}

/** Упражнение в AI-собранной тренировке */
export interface AiWorkoutExercise {
  exercise_id: number
  exercise_name: string
  sets: number
  reps: number
  rest_sec: number
  notes: string
}

/** Ответ AI-сборки тренировки */
export interface AiBuildWorkoutOut {
  name: string
  description: string
  exercises: AiWorkoutExercise[]
}

/** DTO замены упражнения */
export interface AiReplaceExerciseDto {
  exercise_id: number
  reason?: string
}

/** Альтернативное упражнение */
export interface AiAlternative {
  exercise_id: number
  exercise_name: string
  reason: string
}

/** Ответ замены упражнения */
export interface AiReplaceExerciseOut {
  original: string
  alternatives: AiAlternative[]
}

/** Ответ анализа прогресса */
export interface AiAnalyzeProgressOut {
  analysis: string
  highlights: string[]
  trend: 'improving' | 'stable' | 'declining' | 'insufficient_data'
}

/** Одна рекомендация */
export interface AiRecommendation {
  icon: string
  title: string
  text: string
}

/** Ответ рекомендаций */
export interface AiRecommendationsOut {
  recommendations: AiRecommendation[]
  weekly_focus: string
}

// ── API-функции AI Coach ─────────────────────────────────────────────────────

/** AI-сборка тренировки */
const aiBuildWorkoutApi = async (dto: AiBuildWorkoutDto): Promise<AiBuildWorkoutOut> =>
  (await apiClient.post('/ai/build-workout', dto)).data

/** AI-замена упражнения */
const aiReplaceExerciseApi = async (dto: AiReplaceExerciseDto): Promise<AiReplaceExerciseOut> =>
  (await apiClient.post('/ai/replace-exercise', dto)).data

/** AI-анализ прогресса */
const aiAnalyzeProgressApi = async (): Promise<AiAnalyzeProgressOut> =>
  (await apiClient.get('/ai/analyze-progress')).data

/** AI-рекомендации */
const aiRecommendationsApi = async (): Promise<AiRecommendationsOut> =>
  (await apiClient.get('/ai/recommendations')).data

// ── React Query хуки AI Coach ────────────────────────────────────────────────

/** AI-сборка тренировки (мутация) */
export function useAiBuildWorkout() {
  return useMutation({
    mutationFn: aiBuildWorkoutApi,
  })
}

/** AI-замена упражнения (мутация) */
export function useAiReplaceExercise() {
  return useMutation({
    mutationFn: aiReplaceExerciseApi,
  })
}

/** AI-анализ прогресса (мутация — вызывается по клику, не автоматически) */
export function useAiAnalyzeProgress() {
  return useMutation({
    mutationFn: aiAnalyzeProgressApi,
  })
}

/** AI-рекомендации (мутация — вызывается по клику) */
export function useAiRecommendations() {
  return useMutation({
    mutationFn: aiRecommendationsApi,
  })
}
