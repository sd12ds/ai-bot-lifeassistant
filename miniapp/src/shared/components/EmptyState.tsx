/**
 * Заглушка для пустого списка задач.
 * Показывает иконку и призыв к действию.
 */
import { ClipboardList } from 'lucide-react'

interface EmptyStateProps {
  title?: string
  description?: string
}

export function EmptyState({
  title = 'Задач нет',
  description = 'Нажмите + чтобы добавить первую задачу',
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-8 text-center">
      {/* Иконка в градиентном круге */}
      <div
        className="w-20 h-20 rounded-full flex items-center justify-center mb-4"
        style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.2))' }}
      >
        <ClipboardList size={36} style={{ color: '#818cf8' }} />
      </div>
      <p className="text-lg font-semibold mb-1" style={{ color: 'var(--app-text)' }}>
        {title}
      </p>
      <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
        {description}
      </p>
    </div>
  )
}
