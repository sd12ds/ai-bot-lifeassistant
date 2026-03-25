/** SocialMonitorPage — главный дашборд мониторинга соцсетей. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Rss, Activity, BarChart2, XCircle, List } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { fetchSources, fetchSocialStats, fetchSparklines } from '../../../api/social'
import { SourceCard } from './components/SourceCard'
import { PlatformFilterTabs } from './components/PlatformFilterTabs'
import { AddSourceDrawer } from './components/AddSourceDrawer'

export function SocialMonitorPage() {
  const navigate = useNavigate()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [platformFilter, setPlatformFilter] = useState<string | null>(null)

  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['social-sources'],
    queryFn: () => fetchSources(),
    refetchInterval: 30000,
  })

  const { data: stats } = useQuery({
    queryKey: ['social-stats'],
    queryFn: fetchSocialStats,
    refetchInterval: 30000,
  })

  // Загружаем sparkline-данные для всех источников одним batch-запросом
  const sourceIds = sources.map(s => s.id)
  const { data: sparklines = {} } = useQuery({
    queryKey: ['social-sparklines', sourceIds.join(',')],
    queryFn: () => fetchSparklines(sourceIds),
    enabled: sourceIds.length > 0,
    refetchInterval: 60000,
  })

  const filtered = platformFilter ? sources.filter(s => s.platform === platformFilter) : sources

  const widgets = [
    { label: 'Источников',     value: stats?.total_sources ?? 0,    icon: Rss,       color: 'text-[var(--accent)]' },
    { label: 'Активных',       value: stats?.active_sources ?? 0,   icon: Activity,  color: 'text-blue-400' },
    { label: 'Постов за нед.', value: stats?.posts_this_week ?? 0,  icon: BarChart2, color: 'text-green-400' },
    { label: 'С ошибками',     value: stats?.error_sources ?? 0,    icon: XCircle,   color: 'text-red-400' },
  ]

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Мониторинг соцсетей</h1>
        <div className="flex gap-2">
          <button
            onClick={() => navigate('/research/social/feed')}
            className="flex items-center gap-2 px-4 py-2 text-sm border border-[var(--border)] text-[var(--text-secondary)] rounded-lg hover:bg-[var(--bg-hover)] transition-colors"
          >
            <List size={14} /> Лента постов
          </button>
          <button
            onClick={() => setDrawerOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={16} /> Добавить источник
          </button>
        </div>
      </div>

      {/* Stat-карточки */}
      <div className="grid grid-cols-4 gap-4">
        {widgets.map(w => (
          <div key={w.label} className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-[var(--text-muted)]">{w.label}</span>
              <w.icon size={18} className={w.color} />
            </div>
            <div className="text-2xl font-bold">{w.value}</div>
          </div>
        ))}
      </div>

      {/* Platform filter */}
      <PlatformFilterTabs sources={sources} active={platformFilter} onChange={setPlatformFilter} />

      {/* Grid источников */}
      {isLoading ? (
        <div className="text-center py-12 text-[var(--text-muted)]">Загрузка...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 space-y-3">
          <Rss size={40} className="mx-auto text-[var(--text-muted)]" />
          <p className="text-[var(--text-muted)]">Нет источников. Добавьте первый канал или профиль.</p>
          <button onClick={() => setDrawerOpen(true)}
            className="px-5 py-2 bg-[var(--accent)] text-white rounded-lg text-sm hover:bg-[var(--accent-hover)] transition-colors">
            + Добавить источник
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {filtered.map(s => <SourceCard key={s.id} source={s} sparkData={sparklines[s.id]} />)}
        </div>
      )}

      <AddSourceDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  )
}
