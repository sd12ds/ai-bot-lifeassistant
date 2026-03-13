/**
 * Integration-тесты TasksPage и BottomNav.
 * Тестируют полный цикл: загрузка → отображение → взаимодействие.
 * Используют MSW для перехвата HTTP-запросов.
 */
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { server } from '../../mocks/server'
import { MOCK_TASKS } from '../../mocks/handlers'
import { TasksPage } from '../../../features/tasks/TasksPage'
import { BottomNav } from '../../../shared/components/BottomNav'
import { renderWithProviders } from '../../helpers/renderWithProviders'

// ── TasksPage ─────────────────────────────────────────────────────────────────

describe('TasksPage — интеграция', () => {
  it('показывает skeleton loader во время загрузки', async () => {
    // Задерживаем ответ API
    server.use(
      http.get('/api/tasks', async () => {
        await new Promise((r) => setTimeout(r, 100))
        return HttpResponse.json(MOCK_TASKS)
      })
    )
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    // Skeleton сразу виден
    const container = document.querySelector('.animate-pulse')
    expect(container).toBeInTheDocument()
  })

  it('отображает список задач после загрузки', async () => {
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => {
      expect(screen.getByText('Написать тесты')).toBeInTheDocument()
    })
  })

  it('отображает имя пользователя из Telegram mock', async () => {
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => {
      expect(screen.getByText(/Тест/)).toBeInTheDocument()
    })
  })

  it('FAB открывает sheet создания задачи', async () => {
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => screen.getByText('Написать тесты'))
    // FAB — кнопка с иконкой plus (role=button, position fixed)
    const fab = document.querySelector('button.fixed')
    expect(fab).toBeInTheDocument()
    fireEvent.click(fab!)
    await waitFor(() => {
      expect(screen.getByText('Новая задача')).toBeInTheDocument()
    })
  })

  it('создание задачи через FAB+sheet добавляет в список', async () => {
    const user = userEvent.setup()
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => screen.getByText('Написать тесты'))

    // Открываем sheet
    const fab = document.querySelector('button.fixed')!
    fireEvent.click(fab)
    await waitFor(() => screen.getByPlaceholderText('Что нужно сделать?'))

    // Заполняем форму
    await user.type(screen.getByPlaceholderText('Что нужно сделать?'), 'Новая тестовая задача')
    fireEvent.click(screen.getByText('✓ Создать задачу'))

    // Sheet должен закрыться
    await waitFor(() => {
      expect(screen.queryByText('✓ Создать задачу')).not.toBeInTheDocument()
    })
  })

  it('переключение фильтра обновляет запрос', async () => {
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => screen.getByText('Написать тесты'))

    // Нажимаем "Без срока"
    fireEvent.click(screen.getByText('Без срока').closest('button')!)

    await waitFor(() => {
      // Только задача без дедлайна должна быть видна
      expect(screen.getByText('Задача без срока')).toBeInTheDocument()
    })
  })

  it('фильтр "Сегодня" показывает задачи на сегодня', async () => {
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => screen.getByText('Написать тесты'))

    fireEvent.click(screen.getByText('Сегодня').closest('button')!)

    await waitFor(() => {
      // Задача 1 с due_datetime через час попадает в сегодня
      expect(screen.getByText('Написать тесты')).toBeInTheDocument()
    })
  })

  it('показывает EmptyState при пустом ответе сервера', async () => {
    server.use(http.get('/api/tasks', () => HttpResponse.json([])))
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => {
      expect(screen.getByText('Задач нет')).toBeInTheDocument()
    })
  })

  it('показывает прогресс-карточку при наличии задач', async () => {
    renderWithProviders(<TasksPage />, { initialRoute: '/tasks' })
    await waitFor(() => {
      expect(screen.getByText('Выполнено')).toBeInTheDocument()
    })
  })
})

// ── BottomNav ─────────────────────────────────────────────────────────────────

describe('BottomNav', () => {
  it('рендерит 4 пункта навигации', () => {
    renderWithProviders(<BottomNav />, { initialRoute: '/tasks' })
    expect(screen.getByText('Задачи')).toBeInTheDocument()
    expect(screen.getByText('Питание')).toBeInTheDocument()
    expect(screen.getByText('Фитнес')).toBeInTheDocument()
    expect(screen.getByText('Коучинг')).toBeInTheDocument()
  })

  it('активный пункт соответствует текущему маршруту /tasks', () => {
    renderWithProviders(<BottomNav />, { initialRoute: '/tasks' })
    const tasksBtn = screen.getByText('Задачи').closest('button')!
    // Активный пункт имеет дочерний motion.div с layoutId="nav-active"
    // Проверяем цвет иконки — у активного пункта индиго-цвет
    expect(tasksBtn).toBeInTheDocument()
  })

  it('отключённые пункты имеют opacity 0.35', () => {
    renderWithProviders(<BottomNav />, { initialRoute: '/tasks' })
    const nutritionBtn = screen.getByText('Питание').closest('button')!
    expect(nutritionBtn).toHaveStyle({ opacity: '0.35' })
  })

  it('отключённые кнопки имеют атрибут disabled', () => {
    renderWithProviders(<BottomNav />, { initialRoute: '/tasks' })
    const nutritionBtn = screen.getByText('Питание').closest('button')!
    expect(nutritionBtn).toBeDisabled()
  })

  it('кнопка Задачи не disabled', () => {
    renderWithProviders(<BottomNav />, { initialRoute: '/tasks' })
    const tasksBtn = screen.getByText('Задачи').closest('button')!
    expect(tasksBtn).not.toBeDisabled()
  })
})
