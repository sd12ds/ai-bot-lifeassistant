/**
 * GoalDetailPage — детальный экран цели:
 * why_statement, прогресс, этапы (milestones), связанные привычки, история чекинов, AI-инсайт, sticky-кнопки.
 */
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Snowflake, PlayCircle, Trophy, CheckSquare, Square, Loader2 } from 'lucide-react'
import {
  useGoal, useMilestones, useCompleteMilestone,
  useFreezeGoal, useResumeGoal, useAchieveGoal,
  useCheckInHistory,
} from '../../api/coaching'
import { StateIndicator } from './components/StateIndicator'
import { CoachPromptBubble } from './components/CoachPromptBubble'

export function GoalDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const goalId = Number(id)

  const { data: goal, isLoading } = useGoal(goalId)
  const { data: milestones = [] } = useMilestones(goalId)
  const { data: history = [] } = useCheckInHistory({ limit: 5 })

  const completeMilestone = useCompleteMilestone()
  const freezeGoal = useFreezeGoal()
  const resumeGoal = useResumeGoal()
  const achieveGoal = useAchieveGoal()

  if (isLoading) {
    return <div className="flex justify-center items-center min-h-screen"><Loader2 className="animate-spin text-indigo-400" size={30} /></div>
  }
  if (!goal) {
    return <div className="flex justify-center items-center min-h-screen text-gray-400">Цель не найдена</div>
  }

  const pct = Math.round(goal.progress_pct ?? 0)

  return (
    <div className="min-h-screen bg-gray-50 pb-32">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-4 flex items-center gap-3">
        <button onClick={() => navigate('/coaching/goals')} className="text-gray-500">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-lg font-black text-gray-900 flex-1 truncate">{goal.title}</h1>
      </div>

      <div className="px-4 space-y-4">
        {/* Why Statement */}
        {goal.why_statement && (
          <div className="bg-white rounded-2xl p-4 shadow-sm">
            <p className="text-xs text-gray-400 mb-1 uppercase tracking-wide">Зачем мне это</p>
            <p className="text-sm text-gray-700 leading-relaxed">{goal.why_statement}</p>
          </div>
        )}

        {/* Прогресс */}
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-700">Прогресс</span>
            <span className="text-2xl font-black text-indigo-600">{pct}%</span>
          </div>
          <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="h-full bg-indigo-500 rounded-full"
            />
          </div>
          <p className="text-xs text-gray-400 mt-2">{goal.milestones_completed ?? 0} из {goal.milestones_total ?? 0} этапов</p>
        </div>

        {/* Этапы */}
        {milestones.length > 0 && (
          <div className="bg-white rounded-2xl p-4 shadow-sm">
            <p className="text-sm font-semibold text-gray-700 mb-3">Этапы</p>
            <div className="space-y-2">
              {milestones.map(m => (
                <motion.button
                  key={m.id}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => !m.is_completed && completeMilestone.mutate({ goalId, milestoneId: m.id })}
                  className="w-full flex items-center gap-3 p-2 rounded-xl hover:bg-gray-50 transition-colors text-left"
                >
                  {m.is_completed
                    ? <CheckSquare size={20} className="text-green-500 shrink-0" />
                    : <Square size={20} className="text-gray-300 shrink-0" />
                  }
                  <span className={`text-sm ${m.is_completed ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                    {m.title}
                  </span>
                </motion.button>
              ))}
            </div>
          </div>
        )}

        {/* История чекинов */}
        {history.length > 0 && (
          <div className="bg-white rounded-2xl p-4 shadow-sm">
            <p className="text-sm font-semibold text-gray-700 mb-3">Последние чекины</p>
            <div className="space-y-2">
              {history.slice(0, 5).map(c => (
                <div key={c.id} className="flex items-start gap-3 py-1">
                  <div className="flex flex-col items-center gap-1">
                    <span className="text-base">{'⚡'.repeat(Math.min(Math.round((c.energy_level ?? 0) / 2), 5))}</span>
                    <span className="text-xs text-gray-400">{c.energy_level ?? '-'}</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-500 truncate">{c.reflection?.slice(0, 80) ?? '—'}</p>
                    <p className="text-xs text-gray-300 mt-0.5">{new Date(c.created_at).toLocaleDateString('ru-RU')}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* AI-инсайт по цели */}
        {goal.ai_insight && (
          <CoachPromptBubble text={goal.ai_insight} />
        )}
      </div>

      {/* Sticky-кнопки действий */}
      <div className="fixed bottom-0 inset-x-0 bg-white border-t border-gray-100 px-4 py-3 flex gap-2 safe-pb">
        {goal.status === 'active' && (
          <>
            <button
              onClick={() => freezeGoal.mutate({ goalId, data: { reason: 'Временная пауза' } })}
              className="flex-1 flex items-center justify-center gap-1.5 bg-gray-100 text-gray-600 rounded-xl py-3 text-sm font-medium"
            >
              <Snowflake size={16} /> Заморозить
            </button>
            <button
              onClick={() => achieveGoal.mutate(goalId)}
              className="flex-1 flex items-center justify-center gap-1.5 bg-green-500 text-white rounded-xl py-3 text-sm font-semibold"
            >
              <Trophy size={16} /> Достигнуто!
            </button>
          </>
        )}
        {goal.status === 'frozen' && (
          <button
            onClick={() => resumeGoal.mutate(goalId)}
            className="flex-1 flex items-center justify-center gap-1.5 bg-indigo-600 text-white rounded-xl py-3 text-sm font-semibold"
          >
            <PlayCircle size={16} /> Возобновить
          </button>
        )}
      </div>
    </div>
  )
}
