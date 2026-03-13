/**
 * Месячная сетка календаря — классический вид с номерами дней.
 * Дни с записями отмечаются точками.
 * Клик по дню → переключает в DayView.
 */
import type { Task } from '../../api/tasks'
import { toLocalDateStr, isoToLocalDateStr } from './dateUtils'

interface MonthGridProps {
  items: Task[]
  year: number
  month: number // 0-based
  selectedDate: Date
  onSelectDate: (d: Date) => void
}

/** Названия дней недели ПН–ВС */
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

export function MonthGrid({ items, year, month, selectedDate, onSelectDate }: MonthGridProps) {
  const today = new Date()
  const todayStr = toLocalDateStr(today)
  const selectedStr = toLocalDateStr(selectedDate)

  // Считаем, сколько записей на каждый день
  const countByDay: Record<string, number> = {}
  items.forEach((t) => {
    const ref = t.start_at || t.due_datetime
    if (ref) {
      const key = isoToLocalDateStr(ref)
      countByDay[key] = (countByDay[key] || 0) + 1
    }
  })

  // Строим сетку: первый день месяца, сдвиг до понедельника
  const firstDay = new Date(year, month, 1)
  // getDay(): 0=Вс, 1=Пн... → нормализуем в 0=Пн
  const startOffset = (firstDay.getDay() + 6) % 7
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  // Генерируем ячейки: пустые + дни месяца
  const cells: (Date | null)[] = [
    ...Array.from({ length: startOffset }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => new Date(year, month, i + 1)),
  ]

  return (
    <div className="px-3">
      {/* Заголовок дней недели */}
      <div className="grid grid-cols-7 mb-1">
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className="text-center text-[10px] font-medium py-1"
            style={{ color: 'var(--app-hint)' }}
          >
            {d}
          </div>
        ))}
      </div>

      {/* Сетка дней */}
      <div className="grid grid-cols-7 gap-y-0.5">
        {cells.map((date, idx) => {
          if (!date) {
            return <div key={`empty-${idx}`} />
          }
          const dStr = toLocalDateStr(date)
          const isToday = dStr === todayStr
          const isSelected = dStr === selectedStr
          const count = countByDay[dStr] || 0

          return (
            <button
              key={dStr}
              onClick={() => onSelectDate(date)}
              className="flex flex-col items-center justify-center py-1.5 rounded-xl transition-all"
              style={{
                background: isSelected
                  ? 'linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2))'
                  : 'transparent',
              }}
            >
              <span
                className="text-sm font-medium"
                style={{
                  color: isSelected
                    ? '#a78bfa'
                    : isToday
                      ? '#818cf8'
                      : 'var(--app-text)',
                }}
              >
                {date.getDate()}
              </span>
              {/* Точки-индикаторы (до 3) */}
              {count > 0 && (
                <div className="flex gap-0.5 mt-0.5">
                  {Array.from({ length: Math.min(count, 3) }).map((_, j) => (
                    <div
                      key={j}
                      className="w-1 h-1 rounded-full"
                      style={{ background: isSelected ? '#a78bfa' : '#6366f1' }}
                    />
                  ))}
                </div>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
