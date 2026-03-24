/** PostsFeedPage — общая лента постов со всех источников. */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Search } from 'lucide-react'
import { fetchFeed, fetchSources } from '../../../api/social'
import { PostCard } from './components/PostCard'

export function PostsFeedPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [platform, setPlatform] = useState('')
  const [offset, setOffset] = useState(0)
  const LIMIT = 50

  const { data: sources = [] } = useQuery({
    queryKey: ['social-sources'],
    queryFn: () => fetchSources(),
  })

  const { data: feedData, isLoading } = useQuery({
    queryKey: ['social-feed', search, platform, offset],
    queryFn: () => fetchFeed({
      search: search || undefined,
      platform: platform || undefined,
      offset,
      limit: LIMIT,
    }),
    refetchInterval: 60000,
  })

  // sourceMap для PostCard
  const sourceMap = Object.fromEntries(
    sources.map(s => [s.id, { platform: s.platform, source_name: s.source_name }])
  )

  const platforms = [...new Set(sources.map(s => s.platform))]

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/research/social')} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
          <ArrowLeft size={16} />
        </button>
        <h1 className="text-2xl font-bold">Лента постов</h1>
        {feedData && <span className="text-sm text-[var(--text-muted)]">{feedData.total} постов</span>}
      </div>

      {/* Фильтры */}
      <div className="flex gap-3 flex-wrap">
        {/* Поиск */}
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text" value={search}
            onChange={e => { setSearch(e.target.value); setOffset(0) }}
            placeholder="Поиск по тексту..."
            className="w-full pl-9 pr-3 py-2 bg-[var(--bg-hover)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
          />
        </div>

        {/* Фильтр по платформе */}
        <select
          value={platform}
          onChange={e => { setPlatform(e.target.value); setOffset(0) }}
          className="px-3 py-2 bg-[var(--bg-hover)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
        >
          <option value="">Все платформы</option>
          {platforms.map(p => <option key={p} value={p} className="capitalize">{p}</option>)}
        </select>
      </div>

      {/* Лента */}
      {isLoading ? (
        <div className="text-center py-12 text-[var(--text-muted)]">Загрузка...</div>
      ) : feedData?.items.length === 0 ? (
        <div className="text-center py-12 text-[var(--text-muted)]">Постов не найдено</div>
      ) : (
        <div className="space-y-3">
          {feedData?.items.map(p => <PostCard key={p.id} post={p} sourceMap={sourceMap} />)}
        </div>
      )}

      {/* Пагинация */}
      {feedData && feedData.total > LIMIT && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setOffset(Math.max(0, offset - LIMIT))}
            disabled={offset === 0}
            className="px-4 py-1.5 text-sm border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] disabled:opacity-40"
          >← Назад</button>
          <span className="text-sm text-[var(--text-muted)]">
            {offset + 1}–{Math.min(offset + LIMIT, feedData.total)} из {feedData.total}
          </span>
          <button
            onClick={() => setOffset(offset + LIMIT)}
            disabled={offset + LIMIT >= feedData.total}
            className="px-4 py-1.5 text-sm border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] disabled:opacity-40"
          >Вперёд →</button>
        </div>
      )}
    </div>
  )
}
