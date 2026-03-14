/**
 * CoachingDashboard — главный экран модуля коучинга.
 * Показывает: состояние дня, привычки на сегодня, топ-3 цели, AI-инсайт, рекомендации, недельный скор.
 */
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ChevronRight, Loader2, Target, CalendarCheck, Lightbulb } from 'lucide-react'
import {
  useDashboard,
  useLogHabit,
  useMissHabit,
  useDismissRecommendation,
} from '../../api/coaching'
import { StateIndicator } from './components/StateIndicator'
import { GoalCard } from './components/GoalCard'
import { HabitCard } from './components/HabitCard'
import { CoachPromptBubble } from './components/CoachPromptBubble'

export function CoachingDashboard() {
  const navigate = useNavigate()
  const { data: dash, isLoading } = useDashboard()
  const logHabit = useLogHabit()
  const missHabit = useMissHabit()
  const dismissRec = useDismissRecommendation()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="animate-spin text-indigo-500" size={32} />
      </div>
    )
  }

  if (!dash) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 px-8 text-center">
        <span className="text-4xl">🧭</span>
        <p className="text-gray-600 font-medium">Начни свой путь с коучем</p>
        <button
          onClick={() => navigate('/coaching/onboarding')}
          className="bg-indigo-600 text-white px-6 py-3 rounded-2xl font-semibold"
        >
          Начать
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-2">
        <h1 className="text-2xl font-black text-gray-900">Коучинг</h1>
        <p className="text-sm text-gray-500 mt-0.5">{new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}</p>
      </div>

      <div className="px-4 space-y-4">
        {/* Карточка состояния — поле называется state, а не coaching_state */}
        {dash.state && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <StateIndicator state={dash.state} score={dash.weekly_score ?? 0} />
          </motion.div>
        )}

        {/* Привычки сегодня */}
        {dash.habits_today && dash.habits_today.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-bold text-gray-800 flex items-center gap-1.5">
                <CalendarCheck size={16} className="text-purple-500" /> Привычки сегодня
              </h2>
              <button onClick={() => navigate('/coaching/habits')} className="text-xs text-indigo-500 flex items-center gap-0.5">
                Все <ChevronRight size={14} />
              </button>
            </div>
            <div className="space-y-2">
              {dash.habits_today.map((h) => (
                <HabitCard
                  key={h.id}
                  habit={h as any}
                  /* today_done теперь возвращается backend'ом в _habit_to_dict */
                  todayStatus={h.today_done === true ? true : h.today_done === false ? false : undefined}
                  onDone={() => logHabit.mutate(h.id)}
                  onMiss={() => missHabit.mutate(h.id)}
                />
              ))}
            </div>
          </section>
        )}

        {/* AI-инсайт — поле называется top_insight (объект), а не ai_insight (строка) */}
        {dash.top_insight?.body && (
          <CoachPromptBubble
            text={dash.top_insight.body}
            action="Все инсайты"
            onAction={() => navigate('/coaching/insights')}
          />
        )}

        {/* Активные цели — поле называется goals_active, а не active_goals */}
        {dash.goals_active && dash.goals_active.length > 0 && (
          <section>
            <div className="flex items-center justify-between mb-2">
              <h2 className="font-bold text-gray-800 flex items-center gap-1.5">
                <Target size={16} className="text-blue-500" /> Мои цели
              </h2>
              <button onClick={() => navigate('/coaching/goals')} className="text-xs text-indigo-500 flex items-center gap-0.5">
                Все <ChevronRight size={14} />
              </button>
            </div>
            <div className="space-y-2">
              {dash.goals_active.slice(0, 3).map((g) => (
                <GoalCard
                  key={g.id}
                  goal={g as any}
                  compact
                  onClick={() => navigate(`/coaching/goals/${g.id}`)}
                />
              ))}
            </div>
          </section>
        )}

        {/* Рекомендации — поля body и rec_type, а не text и type */}
        {dash.recommendations && dash.recommendations.length > 0 && (
          <section>
            <h2 className="font-bold text-gray-800 flex items-center gap-1.5 mb-2">
              <Lightbulb size={16} className="text-yellow-500" /> Рекомендации
            </h2>
            <div className="space-y-2">
              {dash.recommendations.slice(0, 2).map((r) => (
                <div key={r.id} className="bg-white rounded-2xl p-4 shadow-sm">
                  <p className="text-sm text-gray-700">{r.body}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-gray-400">{r.rec_type}</span>
                    <button
                      onClick={() => dismissRec.mutate(r.id)}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      Скрыть
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Кнопка чекина */}
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => navigate('/coaching/checkin')}
          className="w-full bg-indigo-600 text-white rounded-2xl py-4 font-bold text-base shadow-lg shadow-indigo-200"
        >
          Чекин дня
        </motion.button>
      </div>
    </div>
  )
}
