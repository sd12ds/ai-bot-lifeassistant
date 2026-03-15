/**
 * CoachingDashboard — главный экран модуля коучинга.
 * Показывает: состояние дня, быструю навигацию, привычки, цели, AI-инсайт, рекомендации.
 * Всегда отображает CTA-секции даже при отсутствии данных.
 */
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ChevronRight, Loader2, Target, RefreshCw,
  Lightbulb, BarChart2, Plus, CheckSquare,
} from 'lucide-react'
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

// Карточка быстрой навигации
function QuickNavCard({
  icon, label, sub, onClick, accent = 'bg-white',
}: {
  icon: React.ReactNode
  label: string
  sub?: string
  onClick: () => void
  accent?: string
}) {
  return (
    <motion.button
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className={`${accent} rounded-2xl p-4 shadow-sm flex flex-col items-start gap-1 text-left`}
    >
      <div className="mb-1">{icon}</div>
      <p className="font-bold text-gray-900 text-sm">{label}</p>
      {sub && <p className="text-xs text-gray-400">{sub}</p>}
    </motion.button>
  )
}

export function CoachingDashboard() {
  const navigate = useNavigate()
  const { data: dash, isLoading } = useDashboard()
  const logHabit  = useLogHabit()
  const missHabit = useMissHabit()
  const dismissRec = useDismissRecommendation()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <Loader2 className="animate-spin text-indigo-500" size={32} />
      </div>
    )
  }

  // Если дашборд не загрузился — предлагаем онбординг
  if (!dash) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50 gap-4 px-8 text-center">
        <span className="text-5xl">🧭</span>
        <p className="text-gray-800 font-bold text-xl">Начни с коучем</p>
        <p className="text-gray-500 text-sm">Ставь цели, отслеживай привычки и получай AI-инсайты</p>
        <button
          onClick={() => navigate('/coaching/onboarding')}
          className="bg-indigo-600 text-white px-8 py-3 rounded-2xl font-bold shadow-lg shadow-indigo-200"
        >
          Начать
        </button>
      </div>
    )
  }

  const hasGoals   = dash.goals_active && dash.goals_active.length > 0
  const hasHabits  = dash.habits_today && dash.habits_today.length > 0
  const hasInsight = !!dash.top_insight?.body
  const hasRecs    = dash.recommendations && dash.recommendations.length > 0

  return (
    <div className="min-h-screen bg-gray-50 pb-28">

      {/* ── Шапка с градиентом ── */}
      <div className="bg-gradient-to-br from-indigo-600 to-purple-700 px-4 pt-10 pb-6">
        <h1 className="text-2xl font-black text-white">Коучинг</h1>
        <p className="text-indigo-200 text-sm mt-0.5">
          {new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
        </p>
      </div>

      <div className="px-4 -mt-3 space-y-4">

        {/* ── Карточка состояния ── */}
        {dash.state && (
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <StateIndicator state={dash.state} score={dash.weekly_score ?? 0} />
          </motion.div>
        )}

        {/* ── Кнопка чекина (всегда заметна) ── */}
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => navigate('/coaching/checkin')}
          className="w-full bg-indigo-600 text-white rounded-2xl py-4 font-bold text-base shadow-lg shadow-indigo-200 flex items-center justify-center gap-2"
        >
          <CheckSquare size={20} />
          Чекин дня
        </motion.button>

        {/* ── Быстрая навигация 2×2 ── */}
        <div className="grid grid-cols-2 gap-3">
          <QuickNavCard
            icon={<Target size={20} className="text-blue-500" />}
            label="Мои цели"
            sub={hasGoals ? `${dash.goals_active!.length} активных` : 'Нет целей'}
            onClick={() => navigate('/coaching/goals')}
          />
          <QuickNavCard
            icon={<RefreshCw size={20} className="text-purple-500" />}
            label="Привычки"
            sub={hasHabits ? `${dash.habits_today!.length} на сегодня` : 'Нет привычек'}
            onClick={() => navigate('/coaching/habits')}
          />
          <QuickNavCard
            icon={<Lightbulb size={20} className="text-yellow-500" />}
            label="Инсайты"
            sub="AI-анализ"
            onClick={() => navigate('/coaching/insights')}
          />
          <QuickNavCard
            icon={<BarChart2 size={20} className="text-green-500" />}
            label="Обзор недели"
            sub="Рефлексия"
            onClick={() => navigate('/coaching/review')}
          />
        </div>

        {/* ── AI-инсайт ── */}
        {hasInsight && (
          <CoachPromptBubble
            text={dash.top_insight!.body}
            action="Все инсайты"
            onAction={() => navigate('/coaching/insights')}
          />
        )}

        {/* ── Привычки сегодня ── */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-bold text-gray-800 flex items-center gap-1.5">
              <RefreshCw size={15} className="text-purple-500" /> Привычки сегодня
            </h2>
            <button onClick={() => navigate('/coaching/habits')} className="text-xs text-indigo-500 flex items-center gap-0.5">
              Все <ChevronRight size={14} />
            </button>
          </div>
          {hasHabits ? (
            <div className="space-y-2">
              {dash.habits_today!.map((h) => (
                <HabitCard
                  key={h.id}
                  habit={h as any}
                  todayStatus={h.today_done === true ? true : h.today_done === false ? false : undefined}
                  onDone={() => logHabit.mutate(h.id)}
                  onMiss={() => missHabit.mutate(h.id)}
                />
              ))}
            </div>
          ) : (
            /* Empty state — CTA создать привычку */
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={() => navigate('/coaching/habits')}
              className="w-full bg-white rounded-2xl p-4 shadow-sm flex items-center justify-between text-left"
            >
              <div>
                <p className="font-semibold text-gray-800 text-sm">Нет привычек</p>
                <p className="text-xs text-gray-400 mt-0.5">Добавь первую привычку и начни стрик</p>
              </div>
              <div className="w-8 h-8 bg-purple-100 rounded-xl flex items-center justify-center shrink-0">
                <Plus size={16} className="text-purple-600" />
              </div>
            </motion.button>
          )}
        </section>

        {/* ── Активные цели ── */}
        <section>
          <div className="flex items-center justify-between mb-2">
            <h2 className="font-bold text-gray-800 flex items-center gap-1.5">
              <Target size={15} className="text-blue-500" /> Мои цели
            </h2>
            <button onClick={() => navigate('/coaching/goals')} className="text-xs text-indigo-500 flex items-center gap-0.5">
              Все <ChevronRight size={14} />
            </button>
          </div>
          {hasGoals ? (
            <div className="space-y-2">
              {dash.goals_active!.slice(0, 3).map((g) => (
                <GoalCard
                  key={g.id}
                  goal={g as any}
                  compact
                  onClick={() => navigate(`/coaching/goals/${g.id}`)}
                />
              ))}
            </div>
          ) : (
            /* Empty state — CTA создать цель */
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={() => navigate('/coaching/goals')}
              className="w-full bg-white rounded-2xl p-4 shadow-sm flex items-center justify-between text-left"
            >
              <div>
                <p className="font-semibold text-gray-800 text-sm">Нет активных целей</p>
                <p className="text-xs text-gray-400 mt-0.5">Поставь первую цель — дай себе направление</p>
              </div>
              <div className="w-8 h-8 bg-blue-100 rounded-xl flex items-center justify-center shrink-0">
                <Plus size={16} className="text-blue-600" />
              </div>
            </motion.button>
          )}
        </section>

        {/* ── Рекомендации ── */}
        {hasRecs && (
          <section>
            <h2 className="font-bold text-gray-800 flex items-center gap-1.5 mb-2">
              <Lightbulb size={15} className="text-yellow-500" /> Рекомендации
            </h2>
            <div className="space-y-2">
              {dash.recommendations!.slice(0, 2).map((r) => (
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

      </div>
    </div>
  )
}
