/**
 * CalendarPage — основная страница календаря в Mini App.
 * Поддерживает три вида: день, неделя, месяц.
 * Навигация стрелками ← → переключает период.
 */
import { useState, useMemo } from 'react'
import { toLocalDateStr, isoToLocalDateStr } from './dateUtils'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useCalendarQuery } from '../../api/calendar'
import { TaskSkeletonLoader } from '../../shared/components/Loader'
import { DayView } from './DayView'
import { WeekView } from './WeekView'
import { MonthGrid } from './MonthGrid'
import { EventCard } from './EventCard'

/** Режим отображения */
type ViewMode = 'day' | 'week' | 'month'

/** Названия месяцев для заголовка */
const MONTHS_RU = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
]

/** Возвращает понедельник недели для указанной даты */
function getMonday(d: Date): Date {
  const clone = new Date(d)
  const day = clone.getDay()
  const diff = (day === 0 ? -6 : 1) - day
  clone.setDate(clone.getDate() + diff)
  clone.setHours(0, 0, 0, 0)
  return clone
}

/** Форматирует дату для заголовка */
function formatHeader(date: Date, mode: ViewMode): string {
  if (mode === 'day') {
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'short' })
  }
  if (mode === 'week') {
    const end = new Date(date)
    end.setDate(end.getDate() + 6)
    return `${date.getDate()}–${end.getDate()} ${MONTHS_RU[date.getMonth()]}`
  }
  return `${MONTHS_RU[date.getMonth()]} ${date.getFullYear()}`
}

export function CalendarPage() {
  // Текущая выбранная дата и режим вида
  const [selectedDate, setSelectedDate] = useState(() => new Date())
  const [viewMode, setViewMode] = useState<ViewMode>('week')

  // Вычисляем диапазон запроса в зависимости от режима
  const { dateFrom, dateTo } = useMemo(() => {
    const d = selectedDate
    if (viewMode === 'day') {
      const from = new Date(d.getFullYear(), d.getMonth(), d.getDate())
      const to = new Date(from)
      to.setDate(to.getDate() + 1)
      return { dateFrom: from.toISOString(), dateTo: to.toISOString() }
    }
    if (viewMode === 'week') {
      const mon = getMonday(d)
      const sun = new Date(mon)
      sun.setDate(sun.getDate() + 7)
      return { dateFrom: mon.toISOString(), dateTo: sun.toISOString() }
    }
    // month — весь месяц
    const from = new Date(d.getFullYear(), d.getMonth(), 1)
    const to = new Date(d.getFullYear(), d.getMonth() + 1, 1)
    return { dateFrom: from.toISOString(), dateTo: to.toISOString() }
  }, [selectedDate, viewMode])

  // Загружаем данные
  const { data: items = [], isLoading } = useCalendarQuery(dateFrom, dateTo)

  // Навигация: шаг назад/вперёд
  const navigate = (dir: -1 | 1) => {
    setSelectedDate((prev) => {
      const next = new Date(prev)
      if (viewMode === 'day') next.setDate(next.getDate() + dir)
      else if (viewMode === 'week') next.setDate(next.getDate() + 7 * dir)
      else next.setMonth(next.getMonth() + dir)
      return next
    })
  }

  // Переход на сегодня
  const goToday = () => setSelectedDate(new Date())

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-24">
      {/* ── Шапка: навигация + переключение вида ── */}
      <div className="sticky top-0 z-10 px-4 pt-3 pb-2" style={{ background: 'var(--app-bg)' }}>
        {/* Навигация по периоду */}
        <div className="flex items-center justify-between mb-2">
          <button
            onClick={() => navigate(-1)}
            className="p-1.5 rounded-lg"
            style={{ color: 'var(--app-hint)' }}
          >
            <ChevronLeft size={20} />
          </button>

          <button
            onClick={goToday}
            className="text-sm font-bold px-3 py-1 rounded-lg"
            style={{ color: 'var(--app-text)' }}
          >
            {formatHeader(viewMode === 'week' ? getMonday(selectedDate) : selectedDate, viewMode)}
          </button>

          <button
            onClick={() => navigate(1)}
            className="p-1.5 rounded-lg"
            style={{ color: 'var(--app-hint)' }}
          >
            <ChevronRight size={20} />
          </button>
        </div>

        {/* Переключатель видов */}
        <div
          className="flex rounded-xl p-0.5 border border-white/[0.06]"
          style={{ background: 'rgba(30, 30, 50, 0.5)' }}
        >
          {(['day', 'week', 'month'] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className="flex-1 text-xs font-medium py-1.5 rounded-lg transition-all"
              style={{
                background: viewMode === mode
                  ? 'linear-gradient(135deg, rgba(99,102,241,0.3), rgba(139,92,246,0.2))'
                  : 'transparent',
                color: viewMode === mode ? '#a78bfa' : 'var(--app-hint)',
              }}
            >
              {mode === 'day' ? 'День' : mode === 'week' ? 'Неделя' : 'Месяц'}
            </button>
          ))}
        </div>
      </div>

      {/* ── Контент ── */}
      {isLoading ? (
        <TaskSkeletonLoader />
      ) : viewMode === 'day' ? (
        <DayView items={items} date={selectedDate} />
      ) : viewMode === 'week' ? (
        <WeekView
          items={items}
          weekStart={getMonday(selectedDate)}
          selectedDate={selectedDate}
          onSelectDate={setSelectedDate}
        />
      ) : (
        <>
          <MonthGrid
            items={items}
            year={selectedDate.getFullYear()}
            month={selectedDate.getMonth()}
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
          />
          {/* Список событий выбранного дня под сеткой */}
          <div className="px-4 pt-2 pb-4">
            {items
              .filter((t) => {
                const ref = t.start_at || t.due_datetime
                return ref && isoToLocalDateStr(ref) === toLocalDateStr(selectedDate)
              })
              .map((item) => (
                <EventCard key={item.id} item={item} />
              ))}
          </div>
        </>
      )}
    </div>
  )
}
