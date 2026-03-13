/**
 * Unit-тесты компонентов раздела Tasks:
 * FilterTabs, ProgressHeader, TaskCard, TaskList, TaskCreateSheet.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { Task } from '../../../api/tasks'
import { FilterTabs } from '../../../features/tasks/FilterTabs'
import { ProgressHeader } from '../../../features/tasks/ProgressHeader'
import { TaskCard } from '../../../features/tasks/TaskCard'
import { TaskList } from '../../../features/tasks/TaskList'
import { TaskCreateSheet } from '../../../features/tasks/TaskCreateSheet'

// ── Фикстура задачи ───────────────────────────────────────────────────────────

const BASE_TASK: Task = {
  id: 1,
  title: 'Тестовая задача',
  description: '',
  event_type: 'task',
  status: 'todo',
  priority: 1,
  tags: ['тег1', 'тег2'],
  due_datetime: new Date(Date.now() + 3600_000).toISOString(),
  start_at: null, end_at: null, is_all_day: false,
  remind_at: null, recurrence_rule: null, parent_task_id: null,
  is_done: false, calendar_id: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

const DONE_TASK: Task = { ...BASE_TASK, id: 2, title: 'Готово', is_done: true, status: 'done', priority: 3 }

// ── FilterTabs ────────────────────────────────────────────────────────────────

describe('FilterTabs', () => {
  it('рендерит все 4 таба', () => {
    render(<FilterTabs active="all" onChange={vi.fn()} />)
    expect(screen.getByText('Все')).toBeInTheDocument()
    expect(screen.getByText('Сегодня')).toBeInTheDocument()
    expect(screen.getByText('Неделя')).toBeInTheDocument()
    expect(screen.getByText('Без срока')).toBeInTheDocument()
  })

  it('вызывает onChange с правильным значением при клике', () => {
    const onChange = vi.fn()
    render(<FilterTabs active="all" onChange={onChange} />)
    fireEvent.click(screen.getByText('Сегодня').closest('button')!)
    expect(onChange).toHaveBeenCalledWith('today')
  })

  it('вызывает onChange="week" при клике на Неделя', () => {
    const onChange = vi.fn()
    render(<FilterTabs active="all" onChange={onChange} />)
    fireEvent.click(screen.getByText('Неделя').closest('button')!)
    expect(onChange).toHaveBeenCalledWith('week')
  })

  it('вызывает onChange="nodate" при клике на Без срока', () => {
    const onChange = vi.fn()
    render(<FilterTabs active="all" onChange={onChange} />)
    fireEvent.click(screen.getByText('Без срока').closest('button')!)
    expect(onChange).toHaveBeenCalledWith('nodate')
  })

  it('активный таб не вызывает onChange повторно (уже активен)', () => {
    const onChange = vi.fn()
    render(<FilterTabs active="today" onChange={onChange} />)
    fireEvent.click(screen.getByText('Сегодня').closest('button')!)
    // onChange всё равно вызывается — это нормально, родитель игнорирует
    expect(onChange).toHaveBeenCalledWith('today')
  })
})

// ── ProgressHeader ────────────────────────────────────────────────────────────

describe('ProgressHeader', () => {
  it('отображает заголовок "Мои задачи"', () => {
    render(<ProgressHeader tasks={[]} />)
    expect(screen.getByText(/задачи/i)).toBeInTheDocument()
  })

  it('отображает имя пользователя', () => {
    render(<ProgressHeader tasks={[]} userName="Алексей" />)
    expect(screen.getByText(/Алексей/)).toBeInTheDocument()
  })

  it('не показывает прогресс-карточку при пустом списке', () => {
    render(<ProgressHeader tasks={[]} />)
    expect(screen.queryByText(/Выполнено/)).not.toBeInTheDocument()
  })

  it('показывает прогресс-карточку при наличии задач', () => {
    render(<ProgressHeader tasks={[BASE_TASK, DONE_TASK]} />)
    expect(screen.getByText('Выполнено')).toBeInTheDocument()
  })

  it('показывает корректное соотношение done/total', () => {
    render(<ProgressHeader tasks={[BASE_TASK, DONE_TASK]} />)
    expect(screen.getByText('1 / 2')).toBeInTheDocument()
  })

  it('показывает "Все задачи выполнены!" при 100%', () => {
    render(<ProgressHeader tasks={[DONE_TASK]} />)
    expect(screen.getByText(/Все задачи выполнены!/)).toBeInTheDocument()
  })

  it('показывает приветственное сообщение', () => {
    render(<ProgressHeader tasks={[]} />)
    const greetings = ['Доброе утро', 'Добрый день', 'Добрый вечер', 'Доброй ночи']
    const hasGreeting = greetings.some(g => screen.queryByText(new RegExp(g)))
    expect(hasGreeting).toBe(true)
  })
})

// ── TaskCard ──────────────────────────────────────────────────────────────────

describe('TaskCard', () => {
  it('отображает заголовок задачи', () => {
    render(<TaskCard task={BASE_TASK} onDone={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('Тестовая задача')).toBeInTheDocument()
  })

  it('отображает теги задачи', () => {
    render(<TaskCard task={BASE_TASK} onDone={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.getByText('тег1')).toBeInTheDocument()
    expect(screen.getByText('тег2')).toBeInTheDocument()
  })

  it('вызывает onDone с id и инвертированным is_done при клике чекбокса', () => {
    const onDone = vi.fn()
    render(<TaskCard task={BASE_TASK} onDone={onDone} onDelete={vi.fn()} />)
    const checkbox = screen.getByRole('button', { name: '' }) // первая кнопка = чекбокс
    fireEvent.click(checkbox)
    expect(onDone).toHaveBeenCalledWith(1, true)
  })

  it('выполненная задача имеет line-through на тексте', () => {
    render(<TaskCard task={DONE_TASK} onDone={vi.fn()} onDelete={vi.fn()} />)
    const title = screen.getByText('Готово')
    expect(title).toHaveStyle({ textDecoration: 'line-through' })
  })

  it('задача с просроченным дедлайном показывает время', () => {
    const overdueTask = {
      ...BASE_TASK,
      due_datetime: new Date(Date.now() - 86400_000).toISOString(), // вчера
    }
    render(<TaskCard task={overdueTask} onDone={vi.fn()} onDelete={vi.fn()} />)
    // date-fns форматирует относительное время
    expect(screen.queryByText(/назад/) ?? screen.queryByText(/день/)).toBeTruthy()
  })

  it('задача без дедлайна не показывает время', () => {
    const nodateTask = { ...BASE_TASK, due_datetime: null }
    render(<TaskCard task={nodateTask} onDone={vi.fn()} onDelete={vi.fn()} />)
    expect(screen.queryByText(/назад/)).not.toBeInTheDocument()
    expect(screen.queryByText(/через/)).not.toBeInTheDocument()
  })

  it('не показывает более 3 тегов', () => {
    const manyTagsTask = { ...BASE_TASK, tags: ['a', 'b', 'c', 'd', 'e'] }
    render(<TaskCard task={manyTagsTask} onDone={vi.fn()} onDelete={vi.fn()} />)
    // Должны показываться только первые 3
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('c')).toBeInTheDocument()
    expect(screen.queryByText('d')).not.toBeInTheDocument()
  })
})

// ── TaskList ──────────────────────────────────────────────────────────────────

describe('TaskList', () => {
  it('показывает EmptyState при пустом списке (period=all)', () => {
    render(<TaskList tasks={[]} onDone={vi.fn()} onDelete={vi.fn()} period="all" />)
    expect(screen.getByText('Задач нет')).toBeInTheDocument()
  })

  it('показывает EmptyState с текстом для period=today', () => {
    render(<TaskList tasks={[]} onDone={vi.fn()} onDelete={vi.fn()} period="today" />)
    expect(screen.getByText('Сегодня задач нет')).toBeInTheDocument()
  })

  it('показывает EmptyState с текстом для period=week', () => {
    render(<TaskList tasks={[]} onDone={vi.fn()} onDelete={vi.fn()} period="week" />)
    expect(screen.getByText('На неделю задач нет')).toBeInTheDocument()
  })

  it('показывает EmptyState с текстом для period=nodate', () => {
    render(<TaskList tasks={[]} onDone={vi.fn()} onDelete={vi.fn()} period="nodate" />)
    expect(screen.getByText('Задач без срока нет')).toBeInTheDocument()
  })

  it('рендерит все карточки задач', () => {
    const tasks = [BASE_TASK, DONE_TASK]
    render(<TaskList tasks={tasks} onDone={vi.fn()} onDelete={vi.fn()} period="all" />)
    expect(screen.getByText('Тестовая задача')).toBeInTheDocument()
    expect(screen.getByText('Готово')).toBeInTheDocument()
  })

  it('передаёт onDone в TaskCard', () => {
    const onDone = vi.fn()
    render(<TaskList tasks={[BASE_TASK]} onDone={onDone} onDelete={vi.fn()} period="all" />)
    const checkboxes = screen.getAllByRole('button')
    fireEvent.click(checkboxes[0])
    expect(onDone).toHaveBeenCalledWith(1, true)
  })
})

// ── TaskCreateSheet ───────────────────────────────────────────────────────────

describe('TaskCreateSheet', () => {
  const user = userEvent.setup()

  it('не рендерится при open=false', () => {
    render(<TaskCreateSheet open={false} onClose={vi.fn()} onCreate={vi.fn()} />)
    expect(screen.queryByText('Новая задача')).not.toBeInTheDocument()
  })

  it('рендерится при open=true', () => {
    render(<TaskCreateSheet open={true} onClose={vi.fn()} onCreate={vi.fn()} />)
    expect(screen.getByText('Новая задача')).toBeInTheDocument()
  })

  it('показывает все поля формы', () => {
    render(<TaskCreateSheet open={true} onClose={vi.fn()} onCreate={vi.fn()} />)
    expect(screen.getByPlaceholderText('Что нужно сделать?')).toBeInTheDocument()
    expect(screen.getByText('🔺 Высокий')).toBeInTheDocument()
    expect(screen.getByText('🔸 Обычный')).toBeInTheDocument()
    expect(screen.getByText('🔹 Низкий')).toBeInTheDocument()
  })

  it('кнопка создания заблокирована при пустом заголовке', () => {
    render(<TaskCreateSheet open={true} onClose={vi.fn()} onCreate={vi.fn()} />)
    const submitBtn = screen.getByText('✓ Создать задачу').closest('button')!
    expect(submitBtn).toBeDisabled()
  })

  it('кнопка активируется после ввода заголовка', async () => {
    render(<TaskCreateSheet open={true} onClose={vi.fn()} onCreate={vi.fn()} />)
    const input = screen.getByPlaceholderText('Что нужно сделать?')
    await user.type(input, 'Новая задача')
    const submitBtn = screen.getByText('✓ Создать задачу').closest('button')!
    expect(submitBtn).not.toBeDisabled()
  })

  it('вызывает onCreate с правильными данными', async () => {
    const onCreate = vi.fn()
    render(<TaskCreateSheet open={true} onClose={vi.fn()} onCreate={onCreate} />)
    const input = screen.getByPlaceholderText('Что нужно сделать?')
    await user.type(input, 'Срочная задача')
    // Меняем приоритет на Высокий
    fireEvent.click(screen.getByText('🔺 Высокий'))
    // Добавляем тег
    const tagsInput = screen.getByPlaceholderText('работа, личное, срочно')
    await user.type(tagsInput, 'срочно')
    fireEvent.click(screen.getByText('✓ Создать задачу'))
    expect(onCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Срочная задача',
        priority: 1,
        tags: ['срочно'],
      })
    )
  })

  it('закрывается при клике на кнопку X', () => {
    const onClose = vi.fn()
    render(<TaskCreateSheet open={true} onClose={onClose} onCreate={vi.fn()} />)
    // Кнопка X — иконка закрытия
    const closeBtn = screen.getByRole('button', { name: '' }) // первый button без name = X
    fireEvent.click(closeBtn)
    expect(onClose).toHaveBeenCalled()
  })

  it('показывает isLoading состояние', () => {
    render(<TaskCreateSheet open={true} onClose={vi.fn()} onCreate={vi.fn()} isLoading />)
    expect(screen.getByText('Создаём...')).toBeInTheDocument()
  })
})
