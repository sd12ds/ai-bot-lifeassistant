/**
 * CoachingDashboard — главный экран модуля коучинга.
 * Дизайн соответствует общему стилю приложения: тёмная тема, GlassCard, CSS-переменные.
 */
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ChevronRight, Loader2, Target, RefreshCw,
  Lightbulb, BarChart2, Plus, CheckSquare, History, Sparkles,
} from 'lucide-react'
import {
  useDashboard,
  useLogHabit,
  useMissHabit,
  useDismissRecommendation,
} from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'
import { GoalCard } from './components/GoalCard'
import { HabitCard } from './components/HabitCard'
import { CoachPromptBubble } from './components/CoachPromptBubble'

export function CoachingDashboard() {
  const navigate  = useNavigate()
  const { data: dash, isLoading } = useDashboard()
  const logHabit   = useLogHabit()
  const missHabit  = useMissHabit()
  const dismissRec = useDismissRecommendation()

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="animate-spin" size={32} style={{ color: '#818cf8' }} />
      </div>
    )
  }

  // Нет данных — предлагаем онбординг
  if (!dash) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-4 px-8 text-center">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center text-3xl"
          style={{ background: 'rgba(99,102,241,0.1)' }}
        >
          🧭
        </div>
        <p className="text-base font-bold" style={{ color: 'var(--app-text)' }}>Начни с коучем</p>
        <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
          Ставь цели, отслеживай привычки, получай AI-инсайты
        </p>
        <button
          onClick={() => navigate('/coaching/onboarding')}
          className="px-8 py-3 rounded-2xl font-bold text-white"
          style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
        >
          Начать
        </button>
      </div>
    )
  }

  const hasGoals   = (dash.goals_active?.length ?? 0) > 0
  const hasHabits  = (dash.habits_today?.length ?? 0) > 0
  const hasInsight = !!dash.top_insight?.body
  const hasRecs    = (dash.recommendations?.length ?? 0) > 0

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* ── Шапка ── */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>
            Коучинг
          </h1>
          <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
            {new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        <button
          onClick={() => navigate('/coaching/insights')}
          className="p-2 rounded-xl"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <History size={20} style={{ color: 'var(--app-hint)' }} />
        </button>
      </div>

      {/* ── Скролл-контент ── */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">

        {/* Карточка состояния */}
        {dash.state && (
          <GlassCard className="flex items-center gap-4">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
              style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.25), rgba(139,92,246,0.15))' }}
            >
              🚀
            </div>
            <div className="flex-1">
              <div className="text-xs font-medium mb-0.5" style={{ color: '#a5b4fc' }}>
                Твоё состояние
              </div>
              <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                {dash.state}
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
                {dash.weekly_score ?? 0}
              </div>
              <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>из 100</div>
            </div>
          </GlassCard>
        )}

        {/* AI-инсайт */}
        {hasInsight && (
          <CoachPromptBubble
            text={dash.top_insight!.body}
            action="Все инсайты"
            onAction={() => navigate('/coaching/insights')}
          />
        )}

        {/* ── Быстрые действия ── */}
        <div className="grid grid-cols-3 gap-3">
          {/* Чекин дня — главный CTA */}
          <button
            onClick={() => navigate('/coaching/checkin')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.15))' }}
          >
            <CheckSquare size={20} style={{ color: '#a5b4fc' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Чекин
            </span>
          </button>
          {/* Цели */}
          <button
            onClick={() => navigate('/coaching/goals')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.15), rgba(99,102,241,0.1))' }}
          >
            <Target size={20} style={{ color: '#60a5fa' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Цели
            </span>
          </button>
          {/* Привычки */}
          <button
            onClick={() => navigate('/coaching/habits')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(168,85,247,0.1))' }}
          >
            <RefreshCw size={20} style={{ color: '#c084fc' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Привычки
            </span>
          </button>
          {/* Инсайты */}
          <button
            onClick={() => navigate('/coaching/insights')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            <Lightbulb size={20} style={{ color: '#fbbf24' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Инсайты
            </span>
          </button>
          {/* Обзор недели */}
          <button
            onClick={() => navigate('/coaching/review')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            <BarChart2 size={20} style={{ color: '#34d399' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Обзор
            </span>
          </button>
          {/* AI-анализ */}
          <button
            onClick={() => navigate('/coaching/insights')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1))' }}
          >
            <Sparkles size={20} style={{ color: '#a5b4fc' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              AI-анализ
            </span>
          </button>
        </div>

        {/* ── Привычки сегодня ── */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
              Привычки сегодня
            </span>
            <button
              onClick={() => navigate('/coaching/habits')}
              className="flex items-center gap-0.5 text-xs"
              style={{ color: '#818cf8' }}
            >
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
            // Empty state
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={() => navigate('/coaching/habits')}
              className="w-full rounded-[20px] border border-white/[0.08] p-4 flex items-center justify-between text-left"
              style={{ background: 'var(--glass-bg)' }}
            >
              <div>
                <p className="text-sm font-semibold" style={{ color: 'var(--app-text)' }}>
                  Нет привычек
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--app-hint)' }}>
                  Добавь первую и начни стрик
                </p>
              </div>
              <div
                className="w-8 h-8 rounded-xl flex items-center justify-center"
                style={{ background: 'rgba(168,85,247,0.15)' }}
              >
                <Plus size={16} style={{ color: '#c084fc' }} />
              </div>
            </motion.button>
          )}
        </div>

        {/* ── Активные цели ── */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
              Мои цели
            </span>
            <button
              onClick={() => navigate('/coaching/goals')}
              className="flex items-center gap-0.5 text-xs"
              style={{ color: '#818cf8' }}
            >
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
            // Empty state
            <motion.button
              whileTap={{ scale: 0.97 }}
              onClick={() => navigate('/coaching/goals')}
              className="w-full rounded-[20px] border border-white/[0.08] p-4 flex items-center justify-between text-left"
              style={{ background: 'var(--glass-bg)' }}
            >
              <div>
                <p className="text-sm font-semibold" style={{ color: 'var(--app-text)' }}>
                  Нет активных целей
                </p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--app-hint)' }}>
                  Поставь первую цель — дай себе направление
                </p>
              </div>
              <div
                className="w-8 h-8 rounded-xl flex items-center justify-center"
                style={{ background: 'rgba(59,130,246,0.15)' }}
              >
                <Plus size={16} style={{ color: '#60a5fa' }} />
              </div>
            </motion.button>
          )}
        </div>

        {/* ── Рекомендации ── */}
        {hasRecs && (
          <div>
            <span className="text-xs font-medium block mb-2" style={{ color: 'var(--app-hint)' }}>
              Рекомендации
            </span>
            <div className="space-y-2">
              {dash.recommendations!.slice(0, 2).map((r) => (
                <GlassCard key={r.id}>
                  <p className="text-sm" style={{ color: 'var(--app-text)' }}>{r.body}</p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>{r.rec_type}</span>
                    <button
                      onClick={() => dismissRec.mutate(r.id)}
                      className="text-xs"
                      style={{ color: 'var(--app-hint)' }}
                    >
                      Скрыть
                    </button>
                  </div>
                </GlassCard>
              ))}
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
