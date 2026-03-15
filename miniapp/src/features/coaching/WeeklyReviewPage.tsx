/**
 * WeeklyReviewPage — экран еженедельного обзора.
 * 6 секций: обзор, цели, привычки, AI-саммари, хайлайты/блокеры, приоритеты.
 */
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Loader2, TrendingUp, Target, CalendarCheck, Sparkles, Star, AlertTriangle, ChevronRight } from 'lucide-react'
import { useLatestReview, useWeeklyAnalytics } from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'

export function WeeklyReviewPage() {
  const navigate = useNavigate()
  const { data: review, isLoading } = useLatestReview()
  const { data: analytics } = useWeeklyAnalytics()

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-full">
        <Loader2 className="animate-spin" size={30} style={{ color: '#818cf8' }} />
      </div>
    )
  }

  if (!review && !analytics) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4 px-8 text-center">
        <span className="text-4xl">📊</span>
        <p className="font-medium" style={{ color: 'var(--app-hint)' }}>Обзор будет доступен после первой недели</p>
        <button
          onClick={() => navigate('/coaching')}
          className="text-sm font-semibold"
          style={{ color: '#818cf8' }}
        >
          На главную
        </button>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-4 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/coaching')}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-xl font-black" style={{ color: 'var(--app-text)' }}>Недельный обзор</h1>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
        {/* 1. Обзор недели */}
        {analytics && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
            <GlassCard>
              <p className="text-xs uppercase tracking-wide mb-3 flex items-center gap-1.5" style={{ color: 'var(--app-hint)' }}>
                <TrendingUp size={14} /> Обзор
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <p className="text-2xl font-black" style={{ color: '#818cf8' }}>{analytics.weekly_score ?? '—'}</p>
                  <p className="text-xs" style={{ color: 'var(--app-hint)' }}>Недельный скор</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-black" style={{ color: '#4ade80' }}>{analytics.checkins_count ?? 0}</p>
                  <p className="text-xs" style={{ color: 'var(--app-hint)' }}>Чекинов</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-black" style={{ color: '#fb923c' }}>{analytics.avg_energy?.toFixed(1) ?? '—'}</p>
                  <p className="text-xs" style={{ color: 'var(--app-hint)' }}>Ср. энергия</p>
                </div>
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* 2. Цели */}
        {review?.goals_summary && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
            <GlassCard>
              <p className="text-xs uppercase tracking-wide mb-3 flex items-center gap-1.5" style={{ color: 'var(--app-hint)' }}>
                <Target size={14} /> Цели
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>{review.goals_summary}</p>
              <button
                onClick={() => navigate('/coaching/goals')}
                className="mt-3 text-xs flex items-center gap-1"
                style={{ color: '#818cf8' }}
              >
                Открыть цели <ChevronRight size={12} />
              </button>
            </GlassCard>
          </motion.div>
        )}

        {/* 3. Привычки */}
        {analytics?.habits_stats && analytics.habits_stats.length > 0 && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
            <GlassCard>
              <p className="text-xs uppercase tracking-wide mb-3 flex items-center gap-1.5" style={{ color: 'var(--app-hint)' }}>
                <CalendarCheck size={14} /> Привычки
              </p>
              <div className="space-y-2">
                {analytics.habits_stats.map((h: any) => (
                  <div key={h.id} className="flex items-center gap-3">
                    <span className="text-base">{h.emoji ?? '🎯'}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-0.5">
                        <p className="text-sm truncate" style={{ color: 'var(--app-text)' }}>{h.title}</p>
                        <p className="text-xs font-semibold ml-2" style={{ color: '#a78bfa' }}>{Math.round((h.rate ?? 0) * 100)}%</p>
                      </div>
                      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${(h.rate ?? 0) * 100}%`, background: 'linear-gradient(90deg, #8b5cf6, #6366f1)' }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* 4. AI-саммари */}
        {review?.ai_summary && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
            <div
              className="rounded-[20px] p-4 border border-white/[0.08]"
              style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1))' }}
            >
              <p className="text-xs uppercase tracking-wide mb-2 flex items-center gap-1.5" style={{ color: '#818cf8' }}>
                <Sparkles size={14} /> AI-саммари
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>{review.ai_summary}</p>
            </div>
          </motion.div>
        )}

        {/* 5. Хайлайты и блокеры */}
        {(review?.highlights || review?.blockers) && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <div className="grid grid-cols-2 gap-3">
              {review?.highlights && (
                <div
                  className="rounded-[20px] p-4 border border-white/[0.08]"
                  style={{ background: 'rgba(34,197,94,0.1)' }}
                >
                  <p className="text-xs font-medium flex items-center gap-1 mb-2" style={{ color: '#4ade80' }}>
                    <Star size={13} /> Хайлайты
                  </p>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--app-hint)' }}>{review.highlights}</p>
                </div>
              )}
              {review?.blockers && (
                <div
                  className="rounded-[20px] p-4 border border-white/[0.08]"
                  style={{ background: 'rgba(251,146,60,0.1)' }}
                >
                  <p className="text-xs font-medium flex items-center gap-1 mb-2" style={{ color: '#fb923c' }}>
                    <AlertTriangle size={13} /> Блокеры
                  </p>
                  <p className="text-xs leading-relaxed" style={{ color: 'var(--app-hint)' }}>{review.blockers}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* 6. Приоритеты на следующую неделю */}
        {review?.next_week_priorities && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
            <GlassCard>
              <p className="text-xs uppercase tracking-wide mb-2 flex items-center gap-1.5" style={{ color: 'var(--app-hint)' }}>
                🎯 Приоритеты на следующую неделю
              </p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>{review.next_week_priorities}</p>
            </GlassCard>
          </motion.div>
        )}
      </div>
    </div>
  )
}
