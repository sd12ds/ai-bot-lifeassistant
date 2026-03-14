/** StateIndicator — карточка текущего состояния пользователя (momentum/stable/overload/recovery/risk). */
import type { CoachingState } from '../../../api/coaching'

const STATE_CONFIG: Record<CoachingState, { emoji: string; label: string; color: string; bg: string }> = {
  momentum: { emoji: '🚀', label: 'Ты в потоке', color: 'text-green-600', bg: 'bg-green-50' },
  stable:   { emoji: '✅', label: 'Стабильно', color: 'text-blue-600', bg: 'bg-blue-50' },
  overload: { emoji: '⚡', label: 'Перегруз', color: 'text-orange-600', bg: 'bg-orange-50' },
  recovery: { emoji: '💙', label: 'Восстановление', color: 'text-purple-600', bg: 'bg-purple-50' },
  risk:     { emoji: '⚠️', label: 'Зона риска', color: 'text-red-600', bg: 'bg-red-50' },
}

interface Props {
  state: CoachingState
  score: number
  compact?: boolean
}

export function StateIndicator({ state, score, compact = false }: Props) {
  const cfg = STATE_CONFIG[state]
  if (compact) {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.color}`}>
        {cfg.emoji} {cfg.label}
      </span>
    )
  }
  return (
    <div className={`rounded-2xl p-4 ${cfg.bg}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500 mb-0.5">Твоё состояние</p>
          <p className={`text-lg font-bold ${cfg.color}`}>{cfg.emoji} {cfg.label}</p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-black text-gray-800">{score}</p>
          <p className="text-xs text-gray-400">из 100</p>
        </div>
      </div>
      {/* Score bar */}
      <div className="mt-3 h-1.5 bg-white/60 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${cfg.color.replace('text', 'bg')}`}
             style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}
