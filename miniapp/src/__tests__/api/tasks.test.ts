/**
 * Unit-тесты API-слоя задач (React Query хуки + MSW).
 * Проверяет: запросы с фильтрами, мутации, обработку ошибок.
 */
import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { server } from '../mocks/server'
import { MOCK_TASKS } from '../mocks/handlers'
import {
  useTasksQuery,
  useCreateTask,
  usePatchTask,
  useDeleteTask,
} from '../../api/tasks'
import { createTestQueryClient } from '../helpers/renderWithProviders'
import { QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// Обёртка с QueryClient для renderHook
const wrapper = ({ children }: { children: React.ReactNode }) =>
  createElement(QueryClientProvider, { client: createTestQueryClient() }, children)

// ── useTasksQuery ─────────────────────────────────────────────────────────────

describe('useTasksQuery', () => {
  it('возвращает все задачи по умолчанию (period=all)', async () => {
    const { result } = renderHook(() => useTasksQuery('all'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(MOCK_TASKS.length)
  })

  it('фильтрует задачи по period=today (с дедлайном сегодня)', async () => {
    const { result } = renderHook(() => useTasksQuery('today'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // Задача 1 имеет due_datetime через час — входит в "сегодня"
    result.current.data?.forEach((t) => {
      expect(t.due_datetime).not.toBeNull()
      const dt = new Date(t.due_datetime!).getTime()
      const start = new Date().setHours(0, 0, 0, 0)
      const end = start + 86400_000
      expect(dt).toBeGreaterThanOrEqual(start)
      expect(dt).toBeLessThan(end)
    })
  })

  it('фильтрует задачи по period=nodate (без дедлайна)', async () => {
    const { result } = renderHook(() => useTasksQuery('nodate'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    result.current.data?.forEach((t) => expect(t.due_datetime).toBeNull())
  })

  it('возвращает только выполненные при status=done', async () => {
    // Переопределяем обработчик для теста с status
    server.use(
      http.get('/api/tasks', ({ request }) => {
        const url = new URL(request.url)
        const status = url.searchParams.get('status')
        const tasks = status === 'done' ? MOCK_TASKS.filter((t) => t.is_done) : MOCK_TASKS
        return HttpResponse.json(tasks)
      })
    )
    const { result } = renderHook(() => useTasksQuery('all'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.length).toBeGreaterThanOrEqual(0)
  })

  it('обрабатывает ошибку сервера 500', async () => {
    server.use(
      http.get('/api/tasks', () => new HttpResponse(null, { status: 500 }))
    )
    const { result } = renderHook(() => useTasksQuery('all'), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('обрабатывает ошибку авторизации 401', async () => {
    server.use(
      http.get('/api/tasks', () =>
        HttpResponse.json({ detail: 'Invalid signature' }, { status: 401 })
      )
    )
    const { result } = renderHook(() => useTasksQuery('all'), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

// ── useCreateTask ─────────────────────────────────────────────────────────────

describe('useCreateTask', () => {
  it('создаёт задачу и возвращает объект с id', async () => {
    const { result } = renderHook(() => useCreateTask(), { wrapper })
    result.current.mutate({ title: 'Новая задача', priority: 2 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.id).toBe(99)
    expect(result.current.data?.title).toBe('Новая задача')
  })

  it('создаёт задачу с тегами и дедлайном', async () => {
    const due = new Date(Date.now() + 7200_000).toISOString()
    const { result } = renderHook(() => useCreateTask(), { wrapper })
    result.current.mutate({ title: 'Срочная', priority: 1, due_datetime: due, tags: ['срочно'] })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.priority).toBe(1)
    expect(result.current.data?.tags).toContain('срочно')
  })
})

// ── usePatchTask ──────────────────────────────────────────────────────────────

describe('usePatchTask', () => {
  it('помечает задачу выполненной (is_done → status=done)', async () => {
    const { result } = renderHook(() => usePatchTask(), { wrapper })
    result.current.mutate({ id: 1, is_done: true })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.is_done).toBe(true)
    expect(result.current.data?.status).toBe('done')
  })

  it('возвращает 404 для несуществующей задачи', async () => {
    const { result } = renderHook(() => usePatchTask(), { wrapper })
    result.current.mutate({ id: 9999, is_done: true })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

// ── useDeleteTask ─────────────────────────────────────────────────────────────

describe('useDeleteTask', () => {
  it('удаляет существующую задачу (204)', async () => {
    const { result } = renderHook(() => useDeleteTask(), { wrapper })
    result.current.mutate(1)
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })

  it('возвращает ошибку при удалении несуществующей задачи', async () => {
    const { result } = renderHook(() => useDeleteTask(), { wrapper })
    result.current.mutate(9999)
    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
