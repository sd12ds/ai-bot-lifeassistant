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
    <div className={`bg-white rounded-2xl p-4 shadow-sm transition-all ${isLogged ? 'opacity-80' : ''}`}>
      <div className="flex items-center gap-3">
        {/* Иконка/эмодзи привычки */}
        <div className="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center text-lg shrink-0">
          {habit.emoji ?? '🎯'}
        </div>

        {/* Информация */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-sm text-gray-900 truncate">{habit.title}</p>
          <div className="flex items-center gap-2 mt-0.5">
            {streak > 0 && (
              <span className="text-xs text-orange-500 font-medium">🔥 {streak} дней</span>
            )}
            {showStats && habit.completion_rate !== undefined && (
              <span className="text-xs text-gray-400">{Math.round(habit.completion_rate * 100)}% за месяц</span>
            )}
          </div>
        </div>

        {/* Кнопки логирования или статус */}
        {isLogged ? (
          todayStatus
            ? <CheckCircle className="text-green-500 shrink-0" size={28} />
            : <XCircle className="text-red-400 shrink-0" size={28} />
        ) : (
          <div className="flex items-center gap-2 shrink-0">
            <motion.button
              whileTap={{ scale: 0.85 }}
              onClick={onDone}
              className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center text-green-600"
            >
              <CheckCircle size={22} />
            </motion.button>
            <motion.button
              whileTap={{ scale: 0.85 }}
              onClick={onMiss}
              className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center text-red-400"
            >
              <XCircle size={22} />
            </motion.button>
          </div>
        )}
      </div>
    </div>
  )
}
