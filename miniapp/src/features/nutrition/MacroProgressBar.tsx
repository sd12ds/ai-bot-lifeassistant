/**
 * Горизонтальный прогресс-бар для макронутриента (Б/Ж/У).
 */
import { motion } from 'framer-motion'

interface MacroProgressBarProps {
  label: string
  current: number
  goal: number
  color: string
}

export function MacroProgressBar({ label, current, goal, color }: MacroProgressBarProps) {
  const progress = goal > 0 ? Math.min(current / goal, 1) : 0

  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center">
        <span className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>
          {label}
        </span>
        <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
          {Math.round(current)} / {goal} г
        </span>
      </div>
      {/* Фоновая полоска */}
      <div className="h-2 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.06)' }}>
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${progress * 100}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}
