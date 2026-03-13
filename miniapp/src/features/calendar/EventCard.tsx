/**
 * Компактная карточка события/задачи для календарного вида.
 * Показывает время, название, иконку типа и кнопку «Выполнено» для тренировок.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import type { Task } from '../../api/tasks'
import { apiClient } from '../../api/client'

interface EventCardProps {
  item: Task
  compact?: boolean
}

/** Форматирует ISO-дату в HH:MM */
function fmtTime(iso: string | null): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function EventCard({ item, compact = false }: EventCardProps) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [toggling, setToggling] = useState(false)

  // Клик по workout event → переход к тренировке
  const handleClick = () => {
    if (item.event_type === 'workout') {
      navigate('/fitness/workout')
    }
  }

  // Переключение is_done для задачи
  const handleToggleDone = async (e: React.MouseEvent) => {
    e.stopPropagation()
    setToggling(true)
    try {
      await apiClient.patch(`/tasks/${item.id}`, { is_done: !item.is_done })
      // Инвалидируем кеш календаря и задач
      qc.invalidateQueries({ queryKey: ['calendar'] })
      qc.invalidateQueries({ queryKey: ['tasks'] })
      qc.invalidateQueries({ queryKey: ['fitness', 'next-workout'] })
    } catch (err) {
      console.error('Ошибка обновления:', err)
    } finally {
      setToggling(false)
    }
  }

  // Цвет и иконка по типу
  const accentColor = item.event_type === 'workout'
    ? '#fb923c'
    : item.event_type === 'event' ? '#8b5cf6' : '#6366f1'
  const icon = item.event_type === 'workout'
    ? '🏋️'
    : item.event_type === 'event' ? '📅' : '☑️'

  // Время: пропускаем для is_all_day
  const timeStr = item.is_all_day
    ? ''
    : item.start_at
      ? `${fmtTime(item.start_at)}${item.end_at ? `–${fmtTime(item.end_at)}` : ''}`
      : item.due_datetime
        ? `до ${fmtTime(item.due_datetime)}`
        : ''

  if (compact) {
    return (
      <div
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: accentColor }}
        title={item.title}
      />
    )
  }

  return (
    <div
      className="flex items-start gap-2 rounded-xl px-3 py-2 mb-1.5 border border-white/[0.06]"
      style={{
        background: 'rgba(30, 30, 50, 0.6)',
        borderLeft: `3px solid ${item.is_done ? 'rgba(255,255,255,0.15)' : accentColor}`,
        cursor: item.event_type === 'workout' ? 'pointer' : 'default',
        opacity: item.is_done ? 0.6 : 1,
      }}
      onClick={handleClick}
    >
      {/* Иконка типа */}
      <span className="text-sm mt-0.5">{icon}</span>

      <div className="flex-1 min-w-0">
        {/* Название */}
        <p
          className="text-sm font-medium truncate"
          style={{
            color: item.is_done ? 'var(--app-hint)' : 'var(--app-text)',
            textDecoration: item.is_done ? 'line-through' : 'none',
          }}
        >
          {item.title}
        </p>

        {/* Время */}
        {timeStr && (
          <p className="text-xs mt-0.5" style={{ color: 'var(--app-hint)' }}>
            {timeStr}
          </p>
        )}
      </div>

      {/* Кнопка «Выполнено» для тренировок и задач */}
      <button
        onClick={handleToggleDone}
        disabled={toggling}
        className="shrink-0 px-2 py-1 rounded-lg text-[10px] font-medium"
        style={{
          background: item.is_done
            ? 'rgba(34,197,94,0.2)'
            : 'rgba(255,255,255,0.08)',
          color: item.is_done ? '#22c55e' : 'var(--app-hint)',
          border: 'none',
          opacity: toggling ? 0.5 : 1,
        }}
      >
        {item.is_done ? '✓' : 'Готово'}
      </button>
    </div>
  )
}
