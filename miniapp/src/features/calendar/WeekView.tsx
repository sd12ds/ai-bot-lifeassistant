/**
 * Недельный вид — компактный список дней текущей недели с карточками событий.
 */
import type { Task } from '../../api/tasks'
import { toLocalDateStr, isoToLocalDateStr } from './dateUtils'
import { EventCard } from './EventCard'

interface WeekViewProps {
  items: Task[]
  weekStart: Date
  selectedDate: Date
  onSelectDate: (d: Date) => void
}

/** Короткие названия дней недели (ПН–ВС) */
const DAYS_SHORT = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

/** Возвращает массив 7 дат начиная с weekStart */
function getWeekDays(start: Date): Date[] {
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(start)
    d.setDate(d.getDate() + i)
    return d
  })
}

export function WeekView({ items, weekStart, selectedDate, onSelectDate }: WeekViewProps) {
  const days = getWeekDays(weekStart)
  // Дата сегодня в локальном TZ
  const today = toLocalDateStr(new Date())
  const selectedStr = toLocalDateStr(selectedDate)

  // Группируем записи по дню
  const byDay: Record<string, Task[]> = {}
  items.forEach((t) => {
    const ref = t.start_at || t.due_datetime
    if (ref) {
      const key = isoToLocalDateStr(ref)
      ;(byDay[key] ??= []).push(t)
    }
  })

  return (
    <div>
      {/* Полоска дней недели */}
      <div className="flex justify-between px-3 py-2 mb-2">
        {days.map((d, i) => {
          const dStr = toLocalDateStr(d)
          const isToday = dStr === today
          const isSelected = dStr === selectedStr
          const hasItems = !!byDay[dStr]?.length

          return (
            <button
              key={dStr}
              onClick={() => onSelectDate(d)}
              className="flex flex-col items-center gap-0.5 w-10 py-1 rounded-xl transition-all"
              style={{
                background: isSelected
                  ? 'linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2))'
                  : 'transparent',
              }}
            >
              {/* Название дня */}
              <span
                className="text-[10px] font-medium"
                style={{ color: isSelected ? '#818cf8' : 'var(--app-hint)' }}
              >
                {DAYS_SHORT[i]}
              </span>
              {/* Число */}
              <span
                className="text-sm font-bold"
                style={{
                  color: isSelected ? '#a78bfa' : isToday ? '#818cf8' : 'var(--app-text)',
                }}
              >
                {d.getDate()}
              </span>
              {/* Точка-индикатор наличия записей */}
              {hasItems && (
                <div
                  className="w-1 h-1 rounded-full"
                  style={{ background: isSelected ? '#a78bfa' : '#6366f1' }}
                />
              )}
            </button>
          )
        })}
      </div>

      {/* Список событий выбранного дня */}
      <div className="px-4 pb-4">
        {(byDay[selectedStr] || []).length === 0 ? (
          <p className="text-center text-sm py-6" style={{ color: 'var(--app-hint)' }}>
            Нет записей
          </p>
        ) : (
          byDay[selectedStr].map((item) => <EventCard key={item.id} item={item} />)
        )}
      </div>
    </div>
  )
}
