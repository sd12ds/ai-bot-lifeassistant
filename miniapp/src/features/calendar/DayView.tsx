/**
 * Дневной вид календаря — список событий и задач на выбранный день.
 * Сортировка по времени: сначала события с start_at, затем задачи с due_datetime.
 */
import type { Task } from '../../api/tasks'
import { toLocalDateStr, isoToLocalDateStr } from './dateUtils'
import { EventCard } from './EventCard'
import { EmptyState } from '../../shared/components/EmptyState'

interface DayViewProps {
  items: Task[]
  date: Date
}

export function DayView({ items, date }: DayViewProps) {
  // Фильтруем записи, относящиеся к выбранному дню
  // Дата в локальном TZ
  const dayStr = toLocalDateStr(date)
  const dayItems = items.filter((t) => {
    const ref = t.start_at || t.due_datetime
    return ref && isoToLocalDateStr(ref) === dayStr
  })

  if (dayItems.length === 0) {
    return <EmptyState title="Нет записей" description="На этот день ничего не запланировано" />
  }

  return (
    <div className="flex flex-col gap-1 px-4 pt-2 pb-4">
      {dayItems.map((item) => (
        <EventCard key={item.id} item={item} />
      ))}
    </div>
  )
}
