/** GoalCard — карточка цели со статусом, прогрессом и базовой информацией. */
import { motion } from 'framer-motion'
import type { Goal } from '../../../api/coaching'

// Бэйджи статуса с полупрозрачными тёмными цветами
const STATUS_BADGE: Record<string, { label: string; bg: string; color: string }> = {
  active:   { label: 'Активна',    bg: 'rgba(99,102,241,0.2)',   color: '#818cf8' },
  achieved: { label: 'Достигнута', bg: 'rgba(34,197,94,0.15)',   color: '#4ade80' },
  frozen:   { label: 'Заморожена', bg: 'rgba(100,116,139,0.2)',  color: '#94a3b8' },
  archived: { label: 'В архиве',   bg: 'rgba(100,116,139,0.15)', color: '#64748b' },
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
      className="rounded-[20px] p-4 cursor-pointer border border-white/[0.08]"
      style={{ background: 'var(--glass-bg)' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            {/* Бэйдж статуса */}
            <span
              className="text-xs font-medium px-2 py-0.5 rounded-full"
              style={{ background: badge.bg, color: badge.color }}
            >
              {badge.label}
            </span>
            {goal.priority === 1 && (
              <span className="text-xs" style={{ color: '#fbbf24' }}>★ Главная</span>
            )}
          </div>
          <p className="font-semibold text-sm leading-snug truncate" style={{ color: 'var(--app-text)' }}>
            {goal.title}
          </p>
          {!compact && goal.why_statement && (
            <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--app-hint)' }}>
              {goal.why_statement}
            </p>
          )}
        </div>
        <div className="text-right shrink-0">
          <p className="text-xl font-black" style={{ color: 'var(--app-text)' }}>
            {pct}<span className="text-xs font-normal">%</span>
          </p>
        </div>
      </div>

      {/* Прогресс-бар */}
      <div className="mt-3 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #6366f1, #8b5cf6)' }}
        />
      </div>

      {!compact && (
        <div className="flex items-center justify-between mt-2 text-xs" style={{ color: 'var(--app-hint)' }}>
          <span>{goal.milestones_completed ?? 0}/{goal.milestones_total ?? 0} этапов</span>
          {goal.deadline && <span>до {new Date(goal.deadline).toLocaleDateString('ru-RU')}</span>}
        </div>
      )}
    </motion.div>
  )
}
