/**
 * InsightsPage — экран инсайтов от AI-коуча.
 * Карточки с приоритетами, фильтрация, кнопка "Скрыть".
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Loader2, Sparkles, AlertCircle, Info, Zap } from 'lucide-react'
import { useMarkInsightRead } from '../../api/coaching'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../../api/client'
import { coachingKeys } from '../../api/coaching'

type Priority = 'all' | 'high' | 'medium' | 'low'

const PRIORITY_ICON: Record<string, React.ReactNode> = {
  high:   <AlertCircle size={14} className="text-red-500" />,
  medium: <Zap size={14} className="text-orange-400" />,
  low:    <Info size={14} className="text-blue-400" />,
}

const PRIORITY_LABEL: Record<string, string> = {
  high: 'Важно', medium: 'Заметь', low: 'Интересно',
}

export function InsightsPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Priority>('all')

  // Загружаем инсайты напрямую через apiClient
  const { data: insights = [], isLoading } = useQuery({
    queryKey: coachingKeys.insights,
    queryFn: () => apiClient.get('/coaching/insights').then(r => r.data),
  })

  const markRead = useMarkInsightRead()

  const filtered = filter === 'all'
    ? insights
    : insights.filter((i: any) => i.priority === filter)

  const FILTERS: { key: Priority; label: string }[] = [
    { key: 'all', label: 'Все' },
    { key: 'high', label: 'Важные' },
    { key: 'medium', label: 'Заметь' },
    { key: 'low', label: 'Прочие' },
  ]

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3">
        <button onClick={() => navigate('/coaching')} className="text-gray-500">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-xl font-black text-gray-900 flex-1 flex items-center gap-2">
          <Sparkles size={20} className="text-indigo-500" /> Инсайты
        </h1>
      </div>

      {/* Фильтры */}
      <div className="px-4 pb-4 pt-2 flex gap-2 overflow-x-auto scrollbar-none">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
              filter === f.key
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-white text-gray-600 border border-gray-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Список */}
      <div className="px-4 space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin text-indigo-400" size={28} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <Sparkles size={40} className="text-indigo-200 mx-auto mb-3" />
            <p className="text-gray-500 text-sm">Новых инсайтов пока нет</p>
          </div>
        ) : (
          <AnimatePresence>
            {filtered.map((insight: any, i: number) => (
              <motion.div
                key={insight.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ delay: i * 0.04 }}
                className={`bg-white rounded-2xl p-4 shadow-sm ${insight.is_read ? 'opacity-60' : ''}`}
              >
                <div className="flex items-start gap-3">
                  {/* Иконка приоритета */}
                  <div className="mt-0.5 shrink-0">
                    {PRIORITY_ICON[insight.priority] ?? <Info size={14} className="text-gray-400" />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-gray-400">
                        {PRIORITY_LABEL[insight.priority] ?? insight.priority}
                      </span>
                      <span className="text-xs text-gray-300">
                        {new Date(insight.created_at).toLocaleDateString('ru-RU')}
                      </span>
                    </div>
                    <p className="text-sm text-gray-800 leading-relaxed">{insight.text}</p>
                    {insight.action_text && (
                      <p className="text-xs text-indigo-500 mt-2 font-medium">{insight.action_text}</p>
                    )}
                  </div>
                </div>
                {/* Кнопка "прочитано" */}
                {!insight.is_read && (
                  <div className="flex justify-end mt-2">
                    <button
                      onClick={() => markRead.mutate(insight.id)}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      Скрыть
                    </button>
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}
