/**
 * MSW (Mock Service Worker) обработчики запросов.
 * Перехватывают HTTP-запросы к /api/* в тестах.
 */
import { http, HttpResponse } from 'msw'
import type { Task } from '../../api/tasks'

// ── Фикстура задач ────────────────────────────────────────────────────────────

export const MOCK_TASKS: Task[] = [
  {
    id: 1,
    title: 'Написать тесты',
    description: '',
    event_type: 'task',
    status: 'todo',
    priority: 1,
    tags: ['разработка', 'важно'],
    due_datetime: new Date(Date.now() + 3600_000).toISOString(), // через час
    start_at: null,
    end_at: null,
    is_all_day: false,
    remind_at: null,
    recurrence_rule: null,
    parent_task_id: null,
    is_done: false,
    calendar_id: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 2,
    title: 'Задача без срока',
    description: 'Описание',
    event_type: 'task',
    status: 'todo',
    priority: 2,
    tags: [],
    due_datetime: null,
    start_at: null,
    end_at: null,
    is_all_day: false,
    remind_at: null,
    recurrence_rule: null,
    parent_task_id: null,
    is_done: false,
    calendar_id: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
  {
    id: 3,
    title: 'Выполненная задача',
    description: '',
    event_type: 'task',
    status: 'done',
    priority: 3,
    tags: ['личное'],
    due_datetime: new Date(Date.now() - 86400_000).toISOString(), // вчера
    start_at: null,
    end_at: null,
    is_all_day: false,
    remind_at: null,
    recurrence_rule: null,
    parent_task_id: null,
    is_done: true,
    calendar_id: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
]

// ── Обработчики ───────────────────────────────────────────────────────────────

export const handlers = [
  // GET /api/tasks — с поддержкой фильтров period и status
  http.get('/api/tasks', ({ request }) => {
    const url = new URL(request.url)
    const period = url.searchParams.get('period') ?? 'all'
    const status = url.searchParams.get('status') ?? 'all'

    let tasks = [...MOCK_TASKS]

    // Фильтр статуса
    if (status === 'todo')  tasks = tasks.filter((t) => !t.is_done)
    if (status === 'done')  tasks = tasks.filter((t) => t.is_done)

    // Фильтр периода
    const now = Date.now()
    const dayMs = 86400_000
    if (period === 'today') {
      const start = new Date().setHours(0, 0, 0, 0)
      const end = start + dayMs
      tasks = tasks.filter((t) => {
        if (!t.due_datetime) return false
        const d = new Date(t.due_datetime).getTime()
        return d >= start && d < end
      })
    }
    if (period === 'week') {
      const start = new Date().setHours(0, 0, 0, 0)
      const end = start + 7 * dayMs
      tasks = tasks.filter((t) => {
        if (!t.due_datetime) return false
        const d = new Date(t.due_datetime).getTime()
        return d >= start && d < end
      })
    }
    if (period === 'nodate') {
      tasks = tasks.filter((t) => !t.due_datetime)
    }

    return HttpResponse.json(tasks)
  }),

  // POST /api/tasks
  http.post('/api/tasks', async ({ request }) => {
    const body = await request.json() as Partial<Task>
    const newTask: Task = {
      id: 99,
      title: body.title ?? 'Новая задача',
      description: body.description ?? '',
      event_type: 'task',
      status: 'todo',
      priority: body.priority ?? 2,
      tags: (body.tags as string[]) ?? [],
      due_datetime: body.due_datetime ?? null,
      start_at: null,
      end_at: null,
      is_all_day: false,
      remind_at: null,
      recurrence_rule: null,
      parent_task_id: null,
      is_done: false,
      calendar_id: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(newTask, { status: 201 })
  }),

  // PATCH /api/tasks/:id
  http.patch('/api/tasks/:id', async ({ params, request }) => {
    const id = Number(params.id)
    const body = await request.json() as Partial<Task>
    const existing = MOCK_TASKS.find((t) => t.id === id)
    if (!existing) return new HttpResponse(null, { status: 404 })
    const updated = {
      ...existing,
      ...body,
      status: body.is_done === true ? 'done' : existing.status,
      updated_at: new Date().toISOString(),
    }
    return HttpResponse.json(updated)
  }),

  // DELETE /api/tasks/:id
  http.delete('/api/tasks/:id', ({ params }) => {
    const id = Number(params.id)
    const exists = MOCK_TASKS.some((t) => t.id === id)
    if (!exists) return new HttpResponse(null, { status: 404 })
    return new HttpResponse(null, { status: 204 })
  }),
]
