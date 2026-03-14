/**
 * WeeklyReviewPage — экран еженедельного обзора.
 * 6 секций: обзор, цели, привычки, AI-саммари, хайлайты/блокеры, приоритеты.
 */
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, Loader2, TrendingUp, Target, CalendarCheck, Sparkles, Star, AlertTriangle, ChevronRight } from 'lucide-react'
import { useLatestReview, useWeeklyAnalytics } from '../../api/coaching'

export function WeeklyReviewPage() {
  const navigate = useNavigate()
  const { data: review, isLoading } = useLatestReview()
  const { data: analytics } = useWeeklyAnalytics()

  if (isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <Loader2 className="animate-spin text-indigo-400" size={30} />
      </div>
    )
  }

  if (!review && !analytics) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 px-8 text-center">
        <span className="text-4xl">📊</span>
        <p className="text-gray-600 font-medium">Обзор будет доступен после первой недели</p>
        <button
          onClick={() => navigate('/coaching')}
          className="text-indigo-600 font-semibold text-sm"
        >
          На главную
        </button>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-4 flex items-center gap-3">
        <button onClick={() => navigate('/coaching')} className="text-gray-500">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-xl font-black text-gray-900">Недельный обзор</h1>
      </div>

      <div className="px-4 space-y-4">
        {/* 1. Обзор недели */}
        {analytics && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl p-4 shadow-sm"
          >
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <TrendingUp size={14} /> Обзор
            </p>
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center">
                <p className="text-2xl font-black text-indigo-600">{analytics.weekly_score ?? '—'}</p>
                <p className="text-xs text-gray-400">Недельный скор</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-black text-green-600">{analytics.checkins_count ?? 0}</p>
                <p className="text-xs text-gray-400">Чекинов</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-black text-orange-500">{analytics.avg_energy?.toFixed(1) ?? '—'}</p>
                <p className="text-xs text-gray-400">Ср. энергия</p>
              </div>
            </div>
          </motion.div>
        )}

        {/* 2. Цели */}
        {review?.goals_summary && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
            className="bg-white rounded-2xl p-4 shadow-sm"
          >
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <Target size={14} /> Цели
            </p>
            <p className="text-sm text-gray-700 leading-relaxed">{review.goals_summary}</p>
            <button
              onClick={() => navigate('/coaching/goals')}
              className="mt-3 text-xs text-indigo-500 flex items-center gap-1"
            >
              Открыть цели <ChevronRight size={12} />
            </button>
          </motion.div>
        )}

        {/* 3. Привычки */}
        {analytics?.habits_stats && analytics.habits_stats.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="bg-white rounded-2xl p-4 shadow-sm"
          >
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-1.5">
              <CalendarCheck size={14} /> Привычки
            </p>
            <div className="space-y-2">
              {analytics.habits_stats.map((h: any) => (
                <div key={h.id} className="flex items-center gap-3">
                  <span className="text-base">{h.emoji ?? '🎯'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-0.5">
                      <p className="text-sm text-gray-700 truncate">{h.title}</p>
                      <p className="text-xs font-semibold text-gray-600 ml-2">{Math.round((h.rate ?? 0) * 100)}%</p>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div className="h-full bg-purple-400 rounded-full" style={{ width: `${(h.rate ?? 0) * 100}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        )}

        {/* 4. AI-саммари */}
        {review?.ai_summary && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
            className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl p-4 border border-indigo-100"
          >
            <p className="text-xs text-indigo-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
              <Sparkles size={14} /> AI-саммари
            </p>
            <p className="text-sm text-gray-700 leading-relaxed">{review.ai_summary}</p>
          </motion.div>
        )}

        {/* 5. Хайлайты и блокеры */}
        {(review?.highlights || review?.blockers) && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
            className="grid grid-cols-2 gap-3"
          >
            {review?.highlights && (
              <div className="bg-green-50 rounded-2xl p-4">
                <p className="text-xs text-green-600 font-medium flex items-center gap-1 mb-2">
                  <Star size={13} /> Хайлайты
                </p>
                <p className="text-xs text-gray-600 leading-relaxed">{review.highlights}</p>
              </div>
            )}
            {review?.blockers && (
              <div className="bg-orange-50 rounded-2xl p-4">
                <p className="text-xs text-orange-600 font-medium flex items-center gap-1 mb-2">
                  <AlertTriangle size={13} /> Блокеры
                </p>
                <p className="text-xs text-gray-600 leading-relaxed">{review.blockers}</p>
              </div>
            )}
          </motion.div>
        )}

        {/* 6. Приоритеты на следующую неделю */}
        {review?.next_week_priorities && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}
            className="bg-white rounded-2xl p-4 shadow-sm"
          >
            <p className="text-xs text-gray-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
              🎯 Приоритеты на следующую неделю
            </p>
            <p className="text-sm text-gray-700 leading-relaxed">{review.next_week_priorities}</p>
          </motion.div>
        )}
      </div>
    </div>
  )
}
