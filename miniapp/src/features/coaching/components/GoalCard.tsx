/** GoalCard — карточка цели со статусом, прогрессом и базовой информацией. */
import { motion } from 'framer-motion'
import type { Goal } from '../../../api/coaching'

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  active:   { label: 'Активна', color: 'bg-blue-100 text-blue-700' },
  achieved: { label: 'Достигнута', color: 'bg-green-100 text-green-700' },
  frozen:   { label: 'Заморожена', color: 'bg-gray-100 text-gray-500' },
  archived: { label: 'В архиве', color: 'bg-gray-100 text-gray-400' },
}

interface Props {
  goal: Goal
  onClick?: () => void
  compact?: boolean
}

export function GoalCard({ goal, onClick, compact = false }: Props) {
  const badge = STATUS_BADGE[goal.status] ?? STATUS_BADGE.active
  const pct = Math.round(goal.progress_pct ?? 0)

  return (
    <motion.div
      whileTap={{ scale: 0.97 }}
      onClick={onClick}
      className="bg-white rounded-2xl p-4 shadow-sm cursor-pointer active:bg-gray-50 transition-colors"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badge.color}`}>{badge.label}</span>
            {goal.priority === 1 && <span className="text-xs text-yellow-500">★ Главная</span>}
          </div>
          <p className="font-semibold text-gray-900 text-sm leading-snug truncate">{goal.title}</p>
          {!compact && goal.why_statement && (
            <p className="text-xs text-gray-500 mt-1 line-clamp-2">{goal.why_statement}</p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-xl font-black text-gray-800">{pct}<span className="text-xs font-normal">%</span></p>
        </div>
      </div>
      {/* Прогресс-бар */}
      <div className="mt-3 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      {!compact && (
        <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
          <span>{goal.milestones_completed ?? 0}/{goal.milestones_total ?? 0} этапов</span>
          {goal.deadline && <span>до {new Date(goal.deadline).toLocaleDateString('ru-RU')}</span>}
        </div>
      )}
    </motion.div>
  )
}
