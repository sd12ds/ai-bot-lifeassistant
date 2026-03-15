/**
 * Coaching API — типы, API-функции и React Query хуки.
 * Покрывает все endpoints /api/coaching/*.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

// ══════════════════════════════════════════════════════════════════════════════
// ТИПЫ
// ══════════════════════════════════════════════════════════════════════════════

export type CoachingState = 'momentum' | 'stable' | 'overload' | 'recovery' | 'risk'
export type GoalStatus = 'active' | 'achieved' | 'archived' | 'frozen'
export type HabitFrequency = 'daily' | 'weekly' | 'custom'
export type CoachTone = 'strict' | 'friendly' | 'motivational' | 'soft'
export type CoachingMode = 'soft' | 'standard' | 'active'

export interface Goal {
  id: number
  title: string
  description: string | null
  area: string | null
  status: GoalStatus
  priority: number
  progress_pct: number
  target_date: string | null
  why_statement: string | null
  first_step: string | null
  is_frozen: boolean
  frozen_reason: string | null
  coaching_notes: string | null
  created_at: string
  updated_at: string
  // Доп. поля для GoalCard (опциональны — могут не возвращаться в compact dict)
  deadline?: string | null
  milestones_completed?: number
  milestones_total?: number
  ai_insight?: string | null
}

export interface Milestone {
  id: number
  goal_id: number
  title: string
  status: 'pending' | 'done' | 'skipped'
  due_date: string | null
  description: string | null
  order_index: number
  completed_at: string | null
}

export interface Habit {
  id: number
  title: string
  area: string | null
  frequency: HabitFrequency
  target_count: number
  cue: string | null
  reward: string | null
  best_time: string | null
  is_active: boolean
  current_streak: number
  longest_streak: number
  total_completions: number
  last_logged_at: string | null
  goal_id: number | null
  created_at: string
  // Доп. поля (опциональны)
  emoji?: string
  completion_rate?: number
  today_done?: boolean
}

export interface CheckIn {
  id: number
  goal_id: number | null
  energy_level: number | null  // 1-5
  mood: string | null
  notes: string | null
  blockers: string | null
  wins: string | null
  progress_pct: number | null
  time_slot: string | null    // 'morning' | 'midday' | 'evening' | 'manual'
  check_date: string | null   // YYYY-MM-DD
  created_at: string
}

// Слоты дня: ответ GET /coaching/checkins/by-date
export interface CheckInByDate {
  morning?: CheckIn
  midday?: CheckIn
  evening?: CheckIn
  manual?: CheckIn
}

export interface Review {
  id: number
  goal_id: number | null
  review_type: string
  summary: string | null
  highlights: string[] | null
  blockers: string[] | null
  next_actions: string[] | null
  ai_assessment: string | null
  score: number | null
  created_at: string
  // Доп. поля
  ai_summary?: string | null
  goals_summary?: string | null
  next_week_priorities?: string | null
}

export interface CoachingProfile {
  user_id: number
  coach_tone: CoachTone
  coaching_mode: CoachingMode
  preferred_checkin_time: string | null
  preferred_review_day: string
  morning_brief_enabled: boolean
  evening_reflection_enabled: boolean
  max_daily_nudges: number
}

export interface DashboardData {
  state: CoachingState
  state_score: number
  habits_today: Array<{ id: number; title: string; current_streak: number; longest_streak: number; area: string | null; today_done?: boolean }>
  goals_active: Array<{ id: number; title: string; progress_pct: number; area: string | null; target_date: string | null; is_frozen: boolean; status: string }>
  top_insight: { id: number; insight_type: string; severity: string; title: string; body: string } | null
  recommendations: Array<{ id: number; rec_type: string; title: string; body: string; action_type: string }>
  weekly_score: number
  nudge_pending: Record<string, unknown> | null
  prompt_suggestions: string[]
  risks: { dropout: number; overload: number; goal_failure: number; habit_death: number }
}

export interface OnboardingState {
  current_step: string | null
  steps_completed: string[]
  first_goal_created: boolean
  first_habit_created: boolean
  first_checkin_done: boolean
  bot_onboarding_done: boolean
}

export interface WeeklyAnalytics {
  weekly_score: number
  goals_progress: Array<{ id: number; title: string; progress_pct: number; area: string | null }>
  habits_completion_rate: number
  checkins_this_week: number
  dropout_risk: number
  state: CoachingState
  // Доп. поля (расширенная аналитика)
  checkins_count?: number
  avg_energy?: number
  habits_stats?: Array<{ id: number; title: string; emoji?: string; rate: number }>
}

// ── DTOs ──────────────────────────────────────────────────────────────────────

export interface CreateGoalDto {
  title: string
  description?: string
  area?: string
  target_date?: string
  why_statement?: string
  first_step?: string
  priority?: number
}

export interface UpdateGoalDto {
  title?: string
  description?: string
  area?: string
  target_date?: string | null
  why_statement?: string
  first_step?: string
  priority?: number
  progress_pct?: number
  status?: string
  coaching_notes?: string
}

export interface CreateHabitDto {
  title: string
  area?: string
  frequency?: HabitFrequency
  target_count?: number
  cue?: string
  reward?: string
  best_time?: string
  goal_id?: number
  emoji?: string
}

export interface CreateCheckInDto {
  energy_level?: number
  mood?: string
  notes?: string
  blockers?: string
  wins?: string
  goal_id?: number
  progress_pct?: number
  mood_level?: number
  reflection?: string
  next_priorities?: string
  is_extended?: boolean
  time_slot?: string       // 'morning' | 'midday' | 'evening' | 'manual'
  check_date?: string      // YYYY-MM-DD
}

export interface UpdateProfileDto {
  coach_tone?: CoachTone
  coaching_mode?: CoachingMode
  preferred_checkin_time?: string
  preferred_review_day?: string
  morning_brief_enabled?: boolean
  evening_reflection_enabled?: boolean
  max_daily_nudges?: number
}

// ══════════════════════════════════════════════════════════════════════════════
// API ФУНКЦИИ
// ══════════════════════════════════════════════════════════════════════════════

// -- Dashboard --
const fetchDashboard = async (): Promise<DashboardData> => {
  const { data } = await apiClient.get<DashboardData>('/coaching/dashboard')
  return data
}

// -- Goals --
const fetchGoals = async (status?: string): Promise<Goal[]> => {
  const { data } = await apiClient.get<Goal[]>('/coaching/goals', { params: status ? { status } : undefined })
  return data
}

const fetchGoal = async (id: number): Promise<Goal> => {
  const { data } = await apiClient.get<Goal>(`/coaching/goals/${id}`)
  return data
}

const createGoal = async (dto: CreateGoalDto): Promise<Goal> => {
  const { data } = await apiClient.post<Goal>('/coaching/goals', dto)
  return data
}

const updateGoal = async ({ id, ...dto }: UpdateGoalDto & { id: number }): Promise<Goal> => {
  const { data } = await apiClient.put<Goal>(`/coaching/goals/${id}`, dto)
  return data
}

const freezeGoal = async (id: number): Promise<Goal> => {
  const { data } = await apiClient.post<Goal>(`/coaching/goals/${id}/freeze`)
  return data
}

const resumeGoal = async (id: number): Promise<Goal> => {
  const { data } = await apiClient.post<Goal>(`/coaching/goals/${id}/resume`)
  return data
}

const achieveGoal = async (id: number): Promise<Goal> => {
  const { data } = await apiClient.post<Goal>(`/coaching/goals/${id}/achieve`)
  return data
}

// -- Milestones --
const fetchMilestones = async (goalId: number): Promise<Milestone[]> => {
  const { data } = await apiClient.get<Milestone[]>('/coaching/milestones', { params: { goal_id: goalId } })
  return data
}

const completeMilestone = async (id: number): Promise<Milestone> => {
  const { data } = await apiClient.post<Milestone>(`/coaching/milestones/${id}/complete`)
  return data
}

// -- Habits --
const fetchHabits = async (isActive?: boolean): Promise<Habit[]> => {
  const { data } = await apiClient.get<Habit[]>('/coaching/habits', {
    params: isActive !== undefined ? { is_active: isActive } : undefined,
  })
  return data
}

const createHabit = async (dto: CreateHabitDto): Promise<Habit> => {
  const { data } = await apiClient.post<Habit>('/coaching/habits', dto)
  return data
}

const logHabit = async (id: number): Promise<{ streak: number; is_record: boolean }> => {
  const { data } = await apiClient.post(`/coaching/habits/${id}/log`)
  return data
}

const missHabit = async (id: number): Promise<void> => {
  await apiClient.post(`/coaching/habits/${id}/miss`)
}

const fetchHabitTemplates = async (area?: string) => {
  const { data } = await apiClient.get('/coaching/habits/templates', { params: area ? { area } : undefined })
  return data
}

// -- Check-ins --
const createCheckIn = async (dto: CreateCheckInDto): Promise<CheckIn> => {
  const { data } = await apiClient.post<CheckIn>('/coaching/checkins', dto)
  return data
}

const fetchTodayCheckIn = async () => {
  const { data } = await apiClient.get<{ done: boolean; checkin_id?: number; energy_level?: number }>('/coaching/checkins/today')
  return data
}

const fetchCheckInHistory = async (limit = 20): Promise<CheckIn[]> => {
  const { data } = await apiClient.get<CheckIn[]>('/coaching/checkins/history', { params: { limit } })
  return data
}

// Слоты по дате: GET /coaching/checkins/by-date?date=YYYY-MM-DD
const fetchCheckInByDate = async (date: string): Promise<CheckInByDate> => {
  const { data } = await apiClient.get<CheckInByDate>('/coaching/checkins/by-date', { params: { date } })
  return data
}

// Календарь: GET /coaching/checkins/calendar?days=N → { 'YYYY-MM-DD': ['morning', 'evening'] }
const fetchCheckInCalendar = async (days = 15): Promise<Record<string, string[]>> => {
  const { data } = await apiClient.get<Record<string, string[]>>('/coaching/checkins/calendar', { params: { days } })
  return data
}

// Обновление чекина: PATCH /coaching/checkins/{id}
const updateCheckIn = async ({ id, ...dto }: { id: number } & Partial<CreateCheckInDto>): Promise<CheckIn> => {
  const { data } = await apiClient.patch<CheckIn>(`/coaching/checkins/${id}`, dto)
  return data
}

// -- Reviews --
const fetchLatestReview = async (): Promise<Review | null> => {
  const { data } = await apiClient.get<Review | null>('/coaching/reviews/latest')
  return data
}

// -- Profile --
const fetchProfile = async (): Promise<CoachingProfile> => {
  const { data } = await apiClient.get<CoachingProfile>('/coaching/profile')
  return data
}

const updateProfile = async (dto: UpdateProfileDto): Promise<CoachingProfile> => {
  const { data } = await apiClient.put<CoachingProfile>('/coaching/profile', dto)
  return data
}

// -- Onboarding --
const fetchOnboarding = async (): Promise<OnboardingState> => {
  const { data } = await apiClient.get<OnboardingState>('/coaching/onboarding')
  return data
}

const advanceOnboardingStep = async (step: string) => {
  const { data } = await apiClient.post('/coaching/onboarding/step', { step })
  return data
}

const completeOnboarding = async () => {
  const { data } = await apiClient.post('/coaching/onboarding/complete')
  return data
}

// -- Analytics --
const fetchWeeklyAnalytics = async (): Promise<WeeklyAnalytics> => {
  const { data } = await apiClient.get<WeeklyAnalytics>('/coaching/analytics/weekly')
  return data
}

// -- Recommendations --
const dismissRecommendation = async (id: number) => {
  await apiClient.post(`/coaching/recommendations/${id}/dismiss`)
}

// -- Prompts --
const fetchPrompts = async (context?: string): Promise<string[]> => {
  const { data } = await apiClient.get<string[]>('/coaching/prompts', { params: context ? { context } : undefined })
  return data
}

// -- Insights --
const markInsightRead = async (id: number) => {
  await apiClient.post(`/coaching/insights/${id}/read`)
}

// ══════════════════════════════════════════════════════════════════════════════
// REACT QUERY ХУКИ
// ══════════════════════════════════════════════════════════════════════════════

// Query keys
export const coachingKeys = {
  dashboard: ['coaching', 'dashboard'] as const,
  goals: (status?: string) => ['coaching', 'goals', status] as const,
  goal: (id: number) => ['coaching', 'goal', id] as const,
  milestones: (goalId: number) => ['coaching', 'milestones', goalId] as const,
  habits: (isActive?: boolean) => ['coaching', 'habits', isActive] as const,
  habitTemplates: (area?: string) => ['coaching', 'habit-templates', area] as const,
  todayCheckIn: ['coaching', 'checkin-today'] as const,
  checkInHistory: ['coaching', 'checkin-history'] as const,
  checkInByDate: (date: string) => ['coaching', 'checkin-by-date', date] as const,
  checkInCalendar: (days: number) => ['coaching', 'checkin-calendar', days] as const,
  latestReview: ['coaching', 'review-latest'] as const,
  profile: ['coaching', 'profile'] as const,
  onboarding: ['coaching', 'onboarding'] as const,
  weeklyAnalytics: ['coaching', 'analytics-weekly'] as const,
  prompts: (ctx?: string) => ['coaching', 'prompts', ctx] as const,
  insights: ['coaching', 'insights'] as const,
}

// -- Dashboard --
export function useDashboard() {
  return useQuery({
    queryKey: coachingKeys.dashboard,
    queryFn: fetchDashboard,
    staleTime: 60_000,      // 1 мин — dashboard может кешироваться
    refetchOnWindowFocus: true,
  })
}

// -- Goals --
export function useGoals(status?: string) {
  return useQuery({
    queryKey: coachingKeys.goals(status),
    queryFn: () => fetchGoals(status),
    staleTime: 30_000,
  })
}

export function useGoal(id: number) {
  return useQuery({
    queryKey: coachingKeys.goal(id),
    queryFn: () => fetchGoal(id),
    staleTime: 30_000,
  })
}

export function useMilestones(goalId: number) {
  return useQuery({
    queryKey: coachingKeys.milestones(goalId),
    queryFn: () => fetchMilestones(goalId),
    staleTime: 30_000,
  })
}

export function useCreateGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['coaching', 'goals'] })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

export function useUpdateGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateGoal,
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: coachingKeys.goal(id) })
      qc.invalidateQueries({ queryKey: ['coaching', 'goals'] })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

export function useFreezeGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: freezeGoal,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coaching', 'goals'] }),
  })
}

export function useResumeGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: resumeGoal,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coaching', 'goals'] }),
  })
}

export function useAchieveGoal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: achieveGoal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['coaching', 'goals'] })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

export function useCompleteMilestone() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: completeMilestone,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coaching', 'milestones'] }),
  })
}

// -- Habits --
export function useHabits(isActive?: boolean) {
  return useQuery({
    queryKey: coachingKeys.habits(isActive),
    queryFn: () => fetchHabits(isActive),
    staleTime: 30_000,
  })
}

export function useHabitTemplates(area?: string) {
  return useQuery({
    queryKey: coachingKeys.habitTemplates(area),
    queryFn: () => fetchHabitTemplates(area),
    staleTime: 300_000,   // шаблоны меняются редко
  })
}

export function useCreateHabit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createHabit,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['coaching', 'habits'] })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

export function useLogHabit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: logHabit,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['coaching', 'habits'] })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

export function useMissHabit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: missHabit,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['coaching', 'habits'] }),
  })
}

// -- Check-ins --
export function useTodayCheckIn() {
  return useQuery({
    queryKey: coachingKeys.todayCheckIn,
    queryFn: fetchTodayCheckIn,
    staleTime: 60_000,
  })
}

export function useCheckInHistory(limit = 20) {
  return useQuery({
    queryKey: coachingKeys.checkInHistory,
    queryFn: () => fetchCheckInHistory(limit),
    staleTime: 60_000,
  })
}

export function useCreateCheckIn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createCheckIn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: coachingKeys.todayCheckIn })
      qc.invalidateQueries({ queryKey: ['coaching', 'checkin-by-date'] })
      qc.invalidateQueries({ queryKey: ['coaching', 'checkin-calendar'] })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

// Хук: чекины по конкретной дате (все слоты сразу)
export function useCheckInByDate(date: string) {
  return useQuery({
    queryKey: coachingKeys.checkInByDate(date),
    queryFn: () => fetchCheckInByDate(date),
    staleTime: 60_000,
    enabled: !!date,
  })
}

// Хук: календарь чекинов (dots по дням)
export function useCheckInCalendar(days = 15) {
  return useQuery({
    queryKey: coachingKeys.checkInCalendar(days),
    queryFn: () => fetchCheckInCalendar(days),
    staleTime: 60_000,
  })
}

// Хук: обновление существующего чекина
export function useUpdateCheckIn() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateCheckIn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['coaching', 'checkin-by-date'] })
      qc.invalidateQueries({ queryKey: ['coaching', 'checkin-calendar'] })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

// -- Reviews --
export function useLatestReview() {
  return useQuery({
    queryKey: coachingKeys.latestReview,
    queryFn: fetchLatestReview,
    staleTime: 300_000,
  })
}

// -- Profile --
export function useCoachingProfile() {
  return useQuery({
    queryKey: coachingKeys.profile,
    queryFn: fetchProfile,
    staleTime: 300_000,
  })
}

export function useUpdateCoachingProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateProfile,
    onSuccess: () => qc.invalidateQueries({ queryKey: coachingKeys.profile }),
  })
}

// -- Onboarding --
export function useOnboarding() {
  return useQuery({
    queryKey: coachingKeys.onboarding,
    queryFn: fetchOnboarding,
    staleTime: 300_000,
  })
}

export function useAdvanceOnboarding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: advanceOnboardingStep,
    onSuccess: () => qc.invalidateQueries({ queryKey: coachingKeys.onboarding }),
  })
}

export function useCompleteOnboarding() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: completeOnboarding,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: coachingKeys.onboarding })
      qc.invalidateQueries({ queryKey: coachingKeys.dashboard })
    },
  })
}

// -- Analytics --
export function useWeeklyAnalytics() {
  return useQuery({
    queryKey: coachingKeys.weeklyAnalytics,
    queryFn: fetchWeeklyAnalytics,
    staleTime: 300_000,
  })
}

// -- Recommendations --
export function useDismissRecommendation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: dismissRecommendation,
    onSuccess: () => qc.invalidateQueries({ queryKey: coachingKeys.dashboard }),
  })
}

// -- Prompts --
export function usePrompts(context?: string) {
  return useQuery({
    queryKey: coachingKeys.prompts(context),
    queryFn: () => fetchPrompts(context),
    staleTime: 300_000,
  })
}

// -- Insights --
export function useMarkInsightRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: markInsightRead,
    onSuccess: () => qc.invalidateQueries({ queryKey: coachingKeys.dashboard }),
  })
}
