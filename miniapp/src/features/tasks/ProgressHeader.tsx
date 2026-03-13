/**
 * Шапка страницы задач: имя пользователя, прогресс-бар, количество выполненных.
 */
import { useMemo } from 'react'
import type { Task } from '../../api/tasks'

interface ProgressHeaderProps {
  tasks: Task[]
  userName?: string
}

export function ProgressHeader({ tasks, userName }: ProgressHeaderProps) {
  // Считаем прогресс выполнения
  const { done, total, pct } = useMemo(() => {
    const total = tasks.length
    const done = tasks.filter((t) => t.is_done).length
    const pct = total > 0 ? Math.round((done / total) * 100) : 0
    return { done, total, pct }
  }, [tasks])

  // Приветствие по времени суток
  const greeting = useMemo(() => {
    const h = new Date().getHours()
    if (h < 6) return 'Доброй ночи'
    if (h < 12) return 'Доброе утро'
    if (h < 18) return 'Добрый день'
    return 'Добрый вечер'
  }, [])

  return (
    <div className="px-4 pt-4 pb-2">
      {/* Заголовок */}
      <div className="mb-4">
        <p className="text-sm font-medium mb-0.5" style={{ color: 'var(--app-hint)' }}>
          {greeting}{userName ? `, ${userName}` : ''}
        </p>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
          Мои&nbsp;
          <span className="gradient-text">задачи</span>
        </h1>
      </div>

      {/* Прогресс-карточка */}
      {total > 0 && (
        <div
          className="rounded-[20px] p-4 mb-2"
          style={{
            background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1))',
            border: '1px solid rgba(99,102,241,0.2)',
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Выполнено
            </span>
            <span className="text-sm font-bold gradient-text">
              {done} / {total}
            </span>
          </div>
          {/* Прогресс-бар */}
          <div
            className="h-2 rounded-full overflow-hidden"
            style={{ background: 'rgba(255,255,255,0.08)' }}
          >
            <div
              className="h-full rounded-full transition-all duration-500 gradient-bg"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs mt-1.5" style={{ color: 'var(--app-hint)' }}>
            {pct === 100
              ? '🎉 Все задачи выполнены!'
              : pct > 0
                ? `${100 - pct}% осталось`
                : 'Начни выполнять задачи'}
          </p>
        </div>
      )}
    </div>
  )
}
