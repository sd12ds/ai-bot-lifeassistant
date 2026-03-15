/**
 * InsightsPage — экран инсайтов от AI-коуча.
 * Карточки с приоритетами, фильтрация, кнопка «Скрыть».
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
  high:   <AlertCircle size={14} style={{ color: '#f87171' }} />,
  medium: <Zap size={14} style={{ color: '#fb923c' }} />,
  low:    <Info size={14} style={{ color: '#60a5fa' }} />,
}

const PRIORITY_LABEL: Record<string, string> = {
  high: 'Важно', medium: 'Заметь', low: 'Интересно',
}

export function InsightsPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Priority>('all')

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
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/coaching')}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-xl font-black flex-1 flex items-center gap-2" style={{ color: 'var(--app-text)' }}>
          <Sparkles size={20} style={{ color: '#818cf8' }} /> Инсайты
        </h1>
      </div>

      {/* Фильтры */}
      <div className="px-4 pb-4 pt-2 flex gap-2 overflow-x-auto scrollbar-none shrink-0">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className="shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-all border"
            style={
              filter === f.key
                ? { background: 'rgba(99,102,241,0.25)', color: '#818cf8', borderColor: 'rgba(99,102,241,0.4)' }
                : { background: 'rgba(255,255,255,0.05)', color: 'var(--app-hint)', borderColor: 'rgba(255,255,255,0.08)' }
            }
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Список */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin" size={28} style={{ color: '#818cf8' }} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <Sparkles size={40} className="mx-auto mb-3" style={{ color: 'rgba(129,140,248,0.3)' }} />
            <p className="text-sm" style={{ color: 'var(--app-hint)' }}>Новых инсайтов пока нет</p>
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
                className={`rounded-[20px] p-4 border border-white/[0.08] ${insight.is_read ? 'opacity-50' : ''}`}
                style={{ background: 'var(--glass-bg)' }}
              >
                <div className="flex items-start gap-3">
                  {/* Иконка приоритета */}
                  <div className="mt-0.5 shrink-0">
                    {PRIORITY_ICON[insight.priority] ?? <Info size={14} style={{ color: 'var(--app-hint)' }} />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                        {PRIORITY_LABEL[insight.priority] ?? insight.priority}
                      </span>
                      <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>
                        {new Date(insight.created_at).toLocaleDateString('ru-RU')}
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>{insight.text}</p>
                    {insight.action_text && (
                      <p className="text-xs mt-2 font-medium" style={{ color: '#818cf8' }}>{insight.action_text}</p>
                    )}
                  </div>
                </div>
                {/* Кнопка «прочитано» */}
                {!insight.is_read && (
                  <div className="flex justify-end mt-2">
                    <button
                      onClick={() => markRead.mutate(insight.id)}
                      className="text-xs"
                      style={{ color: 'var(--app-hint)' }}
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
