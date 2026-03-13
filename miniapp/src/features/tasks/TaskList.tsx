/**
 * Анимированный список задач.
 * Поддерживает мультиселект — передаёт selected/selectionMode в каждую карточку.
 */
import { AnimatePresence } from 'framer-motion'
import type { Task } from '../../api/tasks'
import { TaskCard } from './TaskCard'
import { EmptyState } from '../../shared/components/EmptyState'

interface TaskListProps {
  tasks: Task[]
  onDone: (id: number, isDone: boolean) => void
  onDelete: (id: number) => void
  onEdit: (task: Task) => void
  onSelect: (id: number) => void
  selectedIds: Set<number>
  selectionMode: boolean
  period: string
}

const EMPTY_TEXTS: Record<string, { title: string; desc: string }> = {
  all:    { title: 'Задач нет',          desc: 'Нажмите + чтобы добавить первую задачу' },
  today:  { title: 'Сегодня задач нет',  desc: 'Отличный день! Можно добавить задачу на сегодня' },
  week:   { title: 'На неделю задач нет',desc: 'Запланируй задачи на эту неделю' },
  nodate: { title: 'Задач без срока нет',desc: 'Все задачи имеют дедлайн — молодец!' },
}

export function TaskList({
  tasks, onDone, onDelete, onEdit, onSelect,
  selectedIds, selectionMode, period,
}: TaskListProps) {
  if (tasks.length === 0) {
    const empty = EMPTY_TEXTS[period] ?? EMPTY_TEXTS.all
    return <EmptyState title={empty.title} description={empty.desc} />
  }

  return (
    <div className="flex flex-col gap-3 pb-2">
      <AnimatePresence initial={false}>
        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onDone={onDone}
            onDelete={onDelete}
            onEdit={onEdit}
            onSelect={onSelect}
            selected={selectedIds.has(task.id)}
            selectionMode={selectionMode}
          />
        ))}
      </AnimatePresence>
    </div>
  )
}
