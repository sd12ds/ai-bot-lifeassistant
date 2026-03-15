/**
 * GoalDetailPage — детальный экран цели:
 * why_statement, прогресс, этапы (milestones), история чекинов, AI-инсайт, sticky-кнопки.
 */
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Snowflake, PlayCircle, Trophy, CheckSquare, Square, Loader2 } from 'lucide-react'
import {
  useGoal, useMilestones, useCompleteMilestone,
  useFreezeGoal, useResumeGoal, useAchieveGoal,
  useCheckInHistory,
} from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'
import { CoachPromptBubble } from './components/CoachPromptBubble'

export function GoalDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const goalId = Number(id)

  const { data: goal, isLoading } = useGoal(goalId)
  const { data: milestones = [] } = useMilestones(goalId)
  const { data: history = [] } = useCheckInHistory(5)

  const completeMilestone = useCompleteMilestone()
  const freezeGoal = useFreezeGoal()
  const resumeGoal = useResumeGoal()
  const achieveGoal = useAchieveGoal()

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-full">
        <Loader2 className="animate-spin" size={30} style={{ color: '#818cf8' }} />
      </div>
    )
  }
  if (!goal) {
    return (
      <div className="flex justify-center items-center h-full">
        <p style={{ color: 'var(--app-hint)' }}>Цель не найдена</p>
      </div>
    )
  }

  const pct = Math.round(goal.progress_pct ?? 0)

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-4 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/coaching/goals')}
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-lg font-black flex-1 truncate" style={{ color: 'var(--app-text)' }}>
          {goal.title}
        </h1>
      </div>

      {/* Контент */}
      <div className="flex-1 overflow-y-auto px-4 pb-32 space-y-4">
        {/* Why Statement */}
        {goal.why_statement && (
          <GlassCard>
            <p className="text-xs uppercase tracking-wide mb-1" style={{ color: 'var(--app-hint)' }}>Зачем мне это</p>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>{goal.why_statement}</p>
          </GlassCard>
        )}

        {/* Прогресс */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold" style={{ color: 'var(--app-hint)' }}>Прогресс</span>
            <span className="text-2xl font-black" style={{ color: '#818cf8' }}>{pct}%</span>
          </div>
          <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="h-full rounded-full"
              style={{ background: 'linear-gradient(90deg, #6366f1, #8b5cf6)' }}
            />
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--app-hint)' }}>
            {goal.milestones_completed ?? 0} из {goal.milestones_total ?? 0} этапов
          </p>
        </GlassCard>

        {/* Этапы */}
        {milestones.length > 0 && (
          <GlassCard>
            <p className="text-sm font-semibold mb-3" style={{ color: 'var(--app-text)' }}>Этапы</p>
            <div className="space-y-2">
              {milestones.map(m => (
                <motion.button
                  key={m.id}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => !(m.status === 'done') && completeMilestone.mutate(m.id)}
                  className="w-full flex items-center gap-3 p-2 rounded-xl text-left"
                  style={{ background: 'transparent' }}
                >
                  {(m.status === 'done')
                    ? <CheckSquare size={20} style={{ color: '#4ade80' }} className="shrink-0" />
                    : <Square size={20} style={{ color: 'rgba(255,255,255,0.2)' }} className="shrink-0" />
                  }
                  <span
                    className="text-sm"
                    style={{
                      color: (m.status === 'done') ? 'var(--app-hint)' : 'var(--app-text)',
                      textDecoration: (m.status === 'done') ? 'line-through' : 'none',
                    }}
                  >
                    {m.title}
                  </span>
                </motion.button>
              ))}
            </div>
          </GlassCard>
        )}

        {/* История чекинов */}
        {history.length > 0 && (
          <GlassCard>
            <p className="text-sm font-semibold mb-3" style={{ color: 'var(--app-text)' }}>Последние чекины</p>
            <div className="space-y-2">
              {history.slice(0, 5).map(c => (
                <div key={c.id} className="flex items-start gap-3 py-1">
                  <div className="flex flex-col items-center gap-1">
                    <span className="text-base">{'⚡'.repeat(Math.min(Math.round((c.energy_level ?? 0) / 2), 5))}</span>
                    <span className="text-xs" style={{ color: 'var(--app-hint)' }}>{c.energy_level ?? '-'}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs truncate" style={{ color: 'var(--app-hint)' }}>{c.notes?.slice(0, 80) ?? '—'}</p>
                    <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.2)' }}>
                      {new Date(c.created_at).toLocaleDateString('ru-RU')}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        {/* AI-инсайт по цели */}
        {goal.ai_insight && (
          <CoachPromptBubble text={goal.ai_insight} />
        )}
      </div>

      {/* Sticky-кнопки действий */}
      <div
        className="fixed bottom-0 inset-x-0 px-4 py-3 flex gap-2"
        style={{ background: 'var(--app-bg)', borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        {goal.status === 'active' && (
          <>
            <button
              onClick={() => freezeGoal.mutate(goalId)}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-medium border border-white/[0.08]"
              style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
            >
              <Snowflake size={16} /> Заморозить
            </button>
            <button
              onClick={() => achieveGoal.mutate(goalId)}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-semibold"
              style={{ background: 'rgba(34,197,94,0.2)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)' }}
            >
              <Trophy size={16} /> Достигнуто!
            </button>
          </>
        )}
        {goal.status === 'frozen' && (
          <button
            onClick={() => resumeGoal.mutate(goalId)}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-semibold"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
          >
            <PlayCircle size={16} /> Возобновить
          </button>
        )}
      </div>
    </div>
  )
}
