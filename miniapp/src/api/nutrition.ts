/**
 * API-слой модуля питания: типы, запросы, React Query хуки.
 * Все запросы идут через apiClient с авторизацией X-Init-Data.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

// ── Типы ──────────────────────────────────────────────────────────────────────

/** Продукт из справочника (КБЖУ на 100г) */
export interface FoodItem {
  id: number
  name: string
  calories: number | null
  protein_g: number | null
  fat_g: number | null
  carbs_g: number | null
  serving_size_g?: number | null
  is_favorite?: boolean
}

/** Позиция в приёме пищи (КБЖУ на порцию) */
export interface MealItem {
  id: number
  food_item_id: number
  name: string
  amount_g: number
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
}

/** Приём пищи с позициями и итогами */
export interface Meal {
  id: number
  meal_type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  eaten_at: string | null
  notes: string
  items: MealItem[]
  total_calories: number
  total_protein: number
  total_fat: number
  total_carbs: number
  created_at: string | null
}

/** Цели по питанию */
export interface NutritionGoal {
  calories: number | null
  protein_g: number | null
  fat_g: number | null
  carbs_g: number | null
  serving_size_g?: number | null
  water_ml: number
  goal_type: string | null        // lose / maintain / gain
  activity_level: string | null   // sedentary / light / moderate / active / very_active
}

/** Параметры тела пользователя */
export interface Profile {
  weight_kg: number | null
  height_cm: number | null
  age: number | null
  gender: string | null   // male / female
}

/** DTO обновления профиля */
export interface ProfileUpdateDto {
  weight_kg?: number | null
  height_cm?: number | null
  age?: number | null
  gender?: string | null
}

/** Запрос авто-расчёта целей */
export interface GoalsCalculateRequest {
  goal_type: string
  activity_level: string
  weight_kg: number
  height_cm: number
  age: number
  gender: string
  water_ml?: number
}

/** Результат авто-расчёта */
export interface GoalsCalculateResponse {
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
  water_ml: number
}

/** Суммарные КБЖУ за день */
export interface Totals {
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
}

/** Полная сводка за день */
export interface DaySummary {
  date: string
  goals: NutritionGoal | null
  totals: Totals
  water_ml: number
  meals: Meal[]
}

/** Статистика за период */
export interface Stats {
  period: string
  days: number
  avg_calories: number
  avg_protein: number
  avg_fat: number
  avg_carbs: number
  avg_water: number
  daily: DaySummary[]
}

/** Шаблон приёма пищи */
export interface MealTemplate {
  id: number
  name: string
  meal_type: string
  items: MealItem[]
  total_calories: number
  created_at: string | null
}

/** DTO создания шаблона из приёма */
export interface TemplateFromMealDto {
  meal_id: number
  name: string
}

/** Ответ на запрос предложений */
export interface SuggestionsResponse {
  frequent_foods: (FoodItem & { use_count: number })[]
  recent_meals: Meal[]
}

/** DTO позиции при создании приёма пищи */
export interface MealItemCreate {
  name: string
  amount_g: number
  calories: number
  protein_g: number
  fat_g: number
  carbs_g: number
}

/** DTO создания приёма пищи */
export interface MealCreateDto {
  meal_type: string
  eaten_at?: string
  items: MealItemCreate[]
  notes?: string
}

/** DTO обновления целей */
export interface GoalUpdateDto {
  calories?: number | null
  protein_g?: number | null
  fat_g?: number | null
  carbs_g?: number | null
  water_ml?: number | null
  goal_type?: string | null
  activity_level?: string | null
}

// ── API-функции ───────────────────────────────────────────────────────────────

/** Сводка за сегодня */
const fetchToday = async (): Promise<DaySummary> =>
  (await apiClient.get('/nutrition/today')).data

/** Приёмы пищи за период */
const fetchMeals = async (dateFrom: string, dateTo: string): Promise<Meal[]> =>
  (await apiClient.get('/nutrition/meals', { params: { date_from: dateFrom, date_to: dateTo } })).data

/** Один приём пищи */
export const fetchMeal = async (id: number): Promise<Meal> =>
  (await apiClient.get(`/nutrition/meal/${id}`)).data

/** Создание приёма пищи */
const createMeal = async (dto: MealCreateDto): Promise<Meal> =>
  (await apiClient.post('/nutrition/meal', dto)).data

/** Обновление позиций приёма пищи */
const updateMeal = async ({ id, items }: { id: number; items: MealItemCreate[] }): Promise<Meal> =>
  (await apiClient.put(`/nutrition/meal/${id}`, { items })).data

/** Удаление приёма пищи */
const deleteMealApi = async (id: number): Promise<void> =>
  await apiClient.delete(`/nutrition/meal/${id}`)

/** Логирование воды */
const logWaterApi = async (amount_ml: number): Promise<{ id: number; amount_ml: number; logged_at: string }> =>
  (await apiClient.post('/nutrition/water', { amount_ml })).data

/** Вода за дату */
const fetchWater = async (date: string): Promise<{ date: string; total_ml: number }> =>
  (await apiClient.get('/nutrition/water', { params: { date } })).data

/** Текущие цели */
const fetchGoals = async (): Promise<NutritionGoal> =>
  (await apiClient.get('/nutrition/goals')).data

/** Обновление целей */
const updateGoalsApi = async (dto: GoalUpdateDto): Promise<NutritionGoal> =>
  (await apiClient.put('/nutrition/goals', dto)).data

/** Список шаблонов */
const fetchTemplates = async (): Promise<MealTemplate[]> =>
  (await apiClient.get('/nutrition/templates')).data

/** Создать шаблон из приёма пищи */
const createTemplateFromMealApi = async (dto: TemplateFromMealDto): Promise<MealTemplate> =>
  (await apiClient.post('/nutrition/templates/from-meal', dto)).data

/** Удалить шаблон */
const deleteTemplateApi = async (id: number): Promise<void> =>
  await apiClient.delete(`/nutrition/templates/${id}`)

/** Применить шаблон (создать meal) */
const applyTemplateApi = async (id: number): Promise<Meal> =>
  (await apiClient.post(`/nutrition/templates/${id}/apply`)).data

/** Предложения (частые продукты + последние приёмы) */
const fetchSuggestions = async (mealType?: string): Promise<SuggestionsResponse> =>
  (await apiClient.get('/nutrition/suggestions', { params: mealType ? { meal_type: mealType } : {} })).data

/** Список избранных продуктов */
const fetchFavorites = async (): Promise<FoodItem[]> =>
  (await apiClient.get('/nutrition/favorites')).data

/** Toggle избранного */
const toggleFavoriteApi = async (foodItemId: number): Promise<{ food_item_id: number; is_favorite: boolean }> =>
  (await apiClient.post(`/nutrition/favorites/${foodItemId}`)).data

/** Получить профиль (параметры тела) */
const fetchProfile = async (): Promise<Profile> =>
  (await apiClient.get('/nutrition/profile')).data

/** Обновить профиль */
const updateProfileApi = async (dto: ProfileUpdateDto): Promise<Profile> =>
  (await apiClient.put('/nutrition/profile', dto)).data

/** Авто-расчёт целей по параметрам тела */
export const calculateGoalsApi = async (dto: GoalsCalculateRequest): Promise<GoalsCalculateResponse> =>
  (await apiClient.post('/nutrition/goals/calculate', dto)).data

/** Поиск продуктов */
const searchFoodApi = async (q: string): Promise<FoodItem[]> =>
  (await apiClient.get('/nutrition/food/search', { params: { q } })).data

/** Статистика за период */
const fetchStats = async (period: 'week' | 'month'): Promise<Stats> =>
  (await apiClient.get('/nutrition/stats', { params: { period } })).data

// ── React Query хуки ──────────────────────────────────────────────────────────

/** Сводка за сегодня */
export function useNutritionToday() {
  return useQuery({ queryKey: ['nutrition', 'today'], queryFn: fetchToday })
}

/** Сводка за конкретную дату */
export function useNutritionDay(date: string) {
  return useQuery({
    queryKey: ['nutrition', 'day', date],
    queryFn: async () => {
      // Используем meals + water + goals для произвольной даты
      const [meals, water, goals] = await Promise.all([
        fetchMeals(date, date),
        fetchWater(date),
        fetchGoals(),
      ])
      // Рассчитываем итоги
      const totals: Totals = {
        calories: meals.reduce((s, m) => s + m.total_calories, 0),
        protein_g: meals.reduce((s, m) => s + m.total_protein, 0),
        fat_g: meals.reduce((s, m) => s + m.total_fat, 0),
        carbs_g: meals.reduce((s, m) => s + m.total_carbs, 0),
      }
      return { date, goals, totals, water_ml: water.total_ml, meals } as DaySummary
    },
    enabled: !!date,
  })
}

/** Приёмы пищи за период */
export function useMeals(dateFrom: string, dateTo: string) {
  return useQuery({
    queryKey: ['nutrition', 'meals', dateFrom, dateTo],
    queryFn: () => fetchMeals(dateFrom, dateTo),
    enabled: !!dateFrom && !!dateTo,
  })
}

/** Создание приёма пищи */
export function useCreateMeal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createMeal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition'] })
    },
  })
}

/** Обновление приёма пищи */
export function useUpdateMeal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateMeal,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition'] })
    },
  })
}

/** Удаление приёма пищи */
export function useDeleteMeal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteMealApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition'] })
    },
  })
}

/** Логирование воды */
export function useLogWater() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: logWaterApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition'] })
    },
  })
}

/** Цели */
export function useGoals() {
  return useQuery({ queryKey: ['nutrition', 'goals'], queryFn: fetchGoals })
}

/** Обновление целей */
export function useUpdateGoals() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateGoalsApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition', 'goals'] })
      qc.invalidateQueries({ queryKey: ['nutrition', 'today'] })
    },
  })
}

/** Список шаблонов */
export function useTemplates() {
  return useQuery({ queryKey: ['nutrition', 'templates'], queryFn: fetchTemplates })
}

/** Создать шаблон из приёма пищи */
export function useCreateTemplateFromMeal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createTemplateFromMealApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition', 'templates'] })
    },
  })
}

/** Удалить шаблон */
export function useDeleteTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteTemplateApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition', 'templates'] })
    },
  })
}

/** Применить шаблон */
export function useApplyTemplate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: applyTemplateApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition'] })
    },
  })
}

/** Предложения (частые + последние) */
export function useSuggestions(mealType?: string) {
  return useQuery({
    queryKey: ['nutrition', 'suggestions', mealType],
    queryFn: () => fetchSuggestions(mealType),
    staleTime: 60_000,
  })
}

/** Избранные продукты */
export function useFavorites() {
  return useQuery({ queryKey: ['nutrition', 'favorites'], queryFn: fetchFavorites })
}

/** Toggle избранного */
export function useToggleFavorite() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: toggleFavoriteApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition', 'favorites'] })
      qc.invalidateQueries({ queryKey: ['nutrition', 'food', 'search'] })
    },
  })
}

/** Профиль (параметры тела) */
export function useProfile() {
  return useQuery({ queryKey: ['nutrition', 'profile'], queryFn: fetchProfile })
}

/** Обновление профиля */
export function useUpdateProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateProfileApi,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['nutrition', 'profile'] })
    },
  })
}

/** Авто-расчёт целей */
export function useCalculateGoals() {
  return useMutation({ mutationFn: calculateGoalsApi })
}

/** Поиск продуктов с debounce */
export function useFoodSearch(query: string) {
  return useQuery({
    queryKey: ['nutrition', 'food', 'search', query],
    queryFn: () => searchFoodApi(query),
    enabled: query.length >= 2,
    staleTime: 30_000,
  })
}

/** Статистика за период */
export function useNutritionStats(period: 'week' | 'month') {
  return useQuery({
    queryKey: ['nutrition', 'stats', period],
    queryFn: () => fetchStats(period),
  })
}
