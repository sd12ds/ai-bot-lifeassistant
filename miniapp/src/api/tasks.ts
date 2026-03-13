/**
 * React Query хуки для работы с задачами через /api/tasks.
 * Содержит типы Task, хуки для чтения и мутаций.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from './client'

// ── Типы ──────────────────────────────────────────────────────────────────────

export type TaskPriority = 1 | 2 | 3 // 1 высокий, 2 обычный, 3 низкий
export type TaskStatus = 'todo' | 'in_progress' | 'done' | 'cancelled'
export type TaskPeriod = 'all' | 'today' | 'week' | 'nodate'

export interface Task {
  id: number
  title: string
  description: string
  event_type: string
  status: TaskStatus
  priority: TaskPriority
  tags: string[]
  due_datetime: string | null
  start_at: string | null     // начало временного интервала
  end_at: string | null       // конец временного интервала
  is_all_day: boolean
  remind_at: string | null
  recurrence_rule: string | null
  parent_task_id: number | null
  is_done: boolean
  calendar_id: number | null
  created_at: string
  updated_at: string
}

export interface CreateTaskDto {
  title: string
  description?: string
  priority?: TaskPriority
  due_datetime?: string | null
  start_at?: string | null    // начало интервала
  end_at?: string | null      // конец интервала
  tags?: string[]
  remind_at?: string | null   // индивидуальное время уведомления
}

export interface PatchTaskDto {
  title?: string
  status?: TaskStatus
  priority?: TaskPriority
  is_done?: boolean
  due_datetime?: string | null
  start_at?: string | null    // начало интервала
  end_at?: string | null      // конец интервала
  tags?: string[]
  remind_at?: string | null   // индивидуальное время уведомления
}

// ── API функции ───────────────────────────────────────────────────────────────

const fetchTasks = async (period: TaskPeriod = 'all'): Promise<Task[]> => {
  // Запрашиваем задачи с фильтром по периоду
  const params: Record<string, string> = { period }
  const { data } = await apiClient.get<Task[]>('/tasks', { params })
  return data
}

const createTask = async (dto: CreateTaskDto): Promise<Task> => {
  const { data } = await apiClient.post<Task>('/tasks', dto)
  return data
}

const patchTask = async ({ id, ...dto }: PatchTaskDto & { id: number }): Promise<Task> => {
  const { data } = await apiClient.patch<Task>(`/tasks/${id}`, dto)
  return data
}

const deleteTask = async (id: number): Promise<void> => {
  await apiClient.delete(`/tasks/${id}`)
}

// ── React Query хуки ─────────────────────────────────────────────────────────

// Ключ для кеша задач
export const tasksKey = (period: TaskPeriod) => ['tasks', period]

export function useTasksQuery(period: TaskPeriod = 'all') {
  return useQuery({
    queryKey: tasksKey(period),
    queryFn: () => fetchTasks(period),
    staleTime: 30_000, // 30 секунд — не рефетчим лишний раз
  })
}

export function useCreateTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createTask,
    // Инвалидируем все списки задач после создания
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })
}

export function usePatchTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: patchTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })
}

export function useDeleteTask() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteTask,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })
}
