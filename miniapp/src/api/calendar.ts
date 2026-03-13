/**
 * React Query хуки для календарного представления.
 * Запрашивает /api/tasks?view=calendar с диапазоном дат.
 */
import { useQuery } from '@tanstack/react-query'
import { apiClient } from './client'
import type { Task } from './tasks'

// Ключ кеша для календарных запросов
export const calendarKey = (from: string, to: string) => ['calendar', from, to]

/**
 * Загружает все записи (задачи + события) в диапазоне дат.
 */
const fetchCalendarItems = async (dateFrom: string, dateTo: string): Promise<Task[]> => {
  const { data } = await apiClient.get<Task[]>('/tasks', {
    params: { view: 'calendar', date_from: dateFrom, date_to: dateTo },
  })
  return data
}

/**
 * Хук для получения записей календаря за указанный период.
 */
export function useCalendarQuery(dateFrom: string, dateTo: string) {
  return useQuery({
    queryKey: calendarKey(dateFrom, dateTo),
    queryFn: () => fetchCalendarItems(dateFrom, dateTo),
    staleTime: 30_000, // 30 секунд
  })
}
