/** HabitCard — карточка привычки с кнопками ✅/❌ для дневного логирования. */
import { motion } from 'framer-motion'
import { CheckCircle, XCircle } from 'lucide-react'
import type { Habit } from '../../../api/coaching'

interface Props {
  habit: Habit
  /** Статус за сегодня: true=выполнено, false=пропущено, undefined=не отмечено */
  todayStatus?: boolean
  onDone?: () => void
  onMiss?: () => void
  showStats?: boolean
}

export function HabitCard({ habit, todayStatus, onDone, onMiss, showStats = false }: Props) {
  const isLogged = todayStatus !== undefined
  const streak = habit.current_streak ?? 0

  return (
    <div
      className={`rounded-[20px] p-4 border border-white/[0.08] transition-all ${isLogged ? 'opacity-70' : ''}`}
      style={{ background: 'var(--glass-bg)' }}
    >
      <div className="flex items-center gap-3">
        {/* Иконка/эмодзи привычки */}
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-lg shrink-0"
          style={{ background: 'rgba(139,92,246,0.15)' }}
        >
          {habit.emoji ?? '🎯'}
        </div>

        {/* Информация о привычке */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm truncate" style={{ color: 'var(--app-text)' }}>
            {habit.title}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            {streak > 0 && (
              <span className="text-xs font-medium" style={{ color: '#fb923c' }}>🔥 {streak} дней</span>
            )}
            {showStats && habit.completion_rate !== undefined && (
              <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
                {Math.round(habit.completion_rate * 100)}% за месяц
              </span>
            )}
          </div>
        </div>

        {/* Кнопки логирования или статус */}
        {isLogged ? (
          todayStatus
            ? <CheckCircle style={{ color: '#4ade80' }} className="shrink-0" size={28} />
            : <XCircle style={{ color: '#f87171' }} className="shrink-0" size={28} />
        ) : (
          <div className="flex items-center gap-2 shrink-0">
            <motion.button
              whileTap={{ scale: 0.85 }}
              onClick={onDone}
              className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ background: 'rgba(34,197,94,0.15)' }}
            >
              <CheckCircle size={22} style={{ color: '#4ade80' }} />
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.85 }}
              onClick={onMiss}
              className="w-10 h-10 rounded-full flex items-center justify-center"
              style={{ background: 'rgba(239,68,68,0.12)' }}
            >
              <XCircle size={22} style={{ color: '#f87171' }} />
            </motion.button>
          </div>
        )}
      </div>
    </div>
  )
}
