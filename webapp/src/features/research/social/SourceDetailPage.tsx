/** SourceDetailPage — детальная карточка источника с табами. */
import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Play, Pause, RotateCw, Trash2, Save, Loader2 } from 'lucide-react'
import {
  fetchSource, fetchSourcePosts, fetchRuns, updateSource, deleteSource, triggerParse
} from '../../../api/social'
import { PlatformIcon, PlatformBadge } from './components/PlatformBadge'
import { SourceStatusBadge } from './components/SourceStatusBadge'
import { PostCard } from './components/PostCard'
import { ParseRunCard } from './components/ParseRunCard'
import { CollectionConfigPanel } from './components/CollectionConfigPanel'
import { ContentTypeFilter, filterToApiParam } from './components/ContentTypeFilter'
import type { PostTypeFilter } from './components/ContentTypeFilter'
import { SchedulePicker } from './components/SchedulePicker'

const TABS = ['Посты', 'История запусков', 'Настройки'] as const

export function SourceDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [tab, setTab] = useState<typeof TABS[number]>('Посты')
  const [search, setSearch] = useState('')
  const [postTypeFilter, setPostTypeFilter] = useState<PostTypeFilter>('all')
  const [cfgSaved, setCfgSaved] = useState(false)
  const [isParsing, setIsParsing] = useState(false)

  const { data: source, isLoading } = useQuery({
    queryKey: ['social-source', id],
    queryFn: () => fetchSource(id!),
    enabled: !!id,
    refetchInterval: 15000,
  })

  const { data: postsData } = useQuery({
    queryKey: ['social-posts', id, search, postTypeFilter],
    queryFn: () => fetchSourcePosts(id!, { limit: 50, search: search || undefined, post_type: filterToApiParam(postTypeFilter) }),
    enabled: !!id && tab === 'Посты',
  })

  // Загружаем runs всегда — для определения статуса парсинга
  const { data: runs = [] } = useQuery({
    queryKey: ['social-runs', id],
    queryFn: () => fetchRuns(id!),
    enabled: !!id,
    refetchInterval: isParsing ? 3000 : false,
  })

  // Автоопределение завершения парсинга по последнему run
  const latestRun = runs[0]
  if (isParsing && latestRun && latestRun.status !== 'running') {
    setIsParsing(false)
    qc.invalidateQueries({ queryKey: ['social-source', id] })
    qc.invalidateQueries({ queryKey: ['social-posts', id] })
  }

  const toggle = useMutation({
    mutationFn: () => updateSource(id!, { status: source?.status === 'active' ? 'paused' : 'active' } as any),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['social-source', id] }),
  })

  const parse = useMutation({
    mutationFn: () => triggerParse(id!),
    onSuccess: () => {
      setIsParsing(true)
      qc.invalidateQueries({ queryKey: ['social-runs', id] })
    },
    onError: () => setIsParsing(false),
  })

  const del = useMutation({
    mutationFn: () => deleteSource(id!),
    onSuccess: () => navigate('/research/social'),
  })

  // Локальное состояние настроек
  const [localConfig, setLocalConfig] = useState<Record<string, any> | null>(null)
  const cfg = localConfig ?? source?.collection_config ?? {}
  const [intervalHours, setIntervalHours] = useState<number | null>(null)
  const scheduleHours = intervalHours ?? source?.schedule?.interval_hours ?? 6

  const saveConfig = useMutation({
    mutationFn: () => updateSource(id!, {
      collection_config: cfg,
      schedule: { interval_hours: scheduleHours },
    } as any),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['social-source', id] }); setCfgSaved(true); setTimeout(() => setCfgSaved(false), 2000) },
  })

  if (isLoading) return <div className="py-12 text-center text-[var(--text-muted)]">Загрузка...</div>
  if (!source) return <div className="py-12 text-center text-red-400">Источник не найден</div>

  const subs = source.source_meta?.subscribers_count
  const sourceMap = { [source.id]: { platform: source.platform, source_name: source.source_name } }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <button onClick={() => navigate('/research/social')} className="flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
        <ArrowLeft size={14} /> Мониторинг
      </button>

      {/* Header */}
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <PlatformIcon platform={source.platform} size={24} />
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-bold truncate">{source.source_name || source.source_id}</h1>
                <SourceStatusBadge status={source.status} />
              </div>
              <div className="flex items-center gap-3 mt-1">
                <PlatformBadge platform={source.platform} />
                <span className="text-xs text-[var(--text-muted)]">{source.source_url}</span>
                {subs && <span className="text-xs text-[var(--text-muted)]">{subs >= 1000 ? `${(subs/1000).toFixed(1)}K` : subs} подписчиков</span>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button onClick={() => toggle.mutate()} disabled={toggle.isPending}
              className="flex items-center gap-1 px-3 py-1.5 text-sm border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] transition-colors">
              {source.status === 'active' ? <><Pause size={14} /> Пауза</> : <><Play size={14} /> Возобновить</>}
            </button>
            <button onClick={() => parse.mutate()} disabled={parse.isPending || isParsing}
              className="flex items-center gap-1 px-3 py-1.5 text-sm bg-[var(--accent)]/20 text-[var(--accent)] rounded-lg hover:bg-[var(--accent)]/30 transition-colors">
              <RotateCw size={14} className={parse.isPending || isParsing ? 'animate-spin' : ''} />
              {isParsing ? 'Парсинг...' : parse.isPending ? 'Запуск...' : 'Запустить сейчас'}
            </button>
            <button onClick={() => { if (confirm('Удалить источник?')) del.mutate() }}
              className="p-1.5 text-[var(--text-muted)] hover:text-red-400 transition-colors">
              <Trash2 size={16} />
            </button>
          </div>
        </div>

        {/* Mini-stats */}
        <div className="flex gap-6 mt-4 pt-4 border-t border-[var(--border)] text-sm text-[var(--text-muted)]">
          <span>Постов: <span className="text-[var(--text-primary)] font-medium">{postsData?.total ?? '—'}</span></span>
          <span>Последний: <span className="text-[var(--text-primary)] font-medium">{source.last_parsed_at ? new Date(source.last_parsed_at).toLocaleString('ru-RU') : 'никогда'}</span></span>
          <span>Ошибок: <span className={source.error_count > 0 ? 'text-red-400 font-medium' : 'text-[var(--text-primary)] font-medium'}>{source.error_count}</span></span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--border)]">
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px
              ${tab === t ? 'text-[var(--accent)] border-[var(--accent)]' : 'text-[var(--text-muted)] border-transparent hover:text-[var(--text-primary)]'}`}>
            {t}
          </button>
        ))}
      </div>

      {/* Tab: Посты */}
      {tab === 'Посты' && (
        <div className="space-y-4">
          <input
            type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Поиск по тексту..."
            className="w-full px-3 py-2 bg-[var(--bg-hover)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
          />
          <ContentTypeFilter value={postTypeFilter} onChange={setPostTypeFilter} />
          {postsData?.items.length === 0 && <div className="text-center py-8 text-[var(--text-muted)]">Постов пока нет. Запустите парсинг.</div>}
          <div className="space-y-3">
            {postsData?.items.map(p => <PostCard key={p.id} post={p} sourceMap={sourceMap} />)}
          </div>
        </div>
      )}

      {/* Tab: История запусков */}
      {tab === 'История запусков' && (
        <div className="space-y-2">
          {runs.length === 0 && <div className="text-center py-8 text-[var(--text-muted)]">Запусков пока не было.</div>}
          {runs.map(r => <ParseRunCard key={r.id} run={r} />)}
        </div>
      )}

      {/* Tab: Настройки */}
      {tab === 'Настройки' && (
        <div className="max-w-lg space-y-6">
          <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-5 space-y-5">
            <h3 className="font-medium text-[var(--text-primary)]">Параметры сбора</h3>
            <CollectionConfigPanel
              platform={source.platform}
              resultsType={cfg.results_type ?? 'posts'}
              onResultsTypeChange={v => setLocalConfig({ ...cfg, results_type: v })}
              extras={{ metrics: cfg.metrics ?? true, media: cfg.media ?? true, hashtags: cfg.hashtags ?? false, mentions: cfg.mentions ?? false }}
              onExtrasChange={(k, v) => setLocalConfig({ ...cfg, [k]: v })}
              limit={cfg.limit ?? 50}
              onLimitChange={v => setLocalConfig({ ...cfg, limit: v })}
            />
          </div>
          <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-5 space-y-3">
            <h3 className="font-medium text-[var(--text-primary)]">Расписание</h3>
            <SchedulePicker value={scheduleHours} onChange={setIntervalHours} />
          </div>
          <button onClick={() => saveConfig.mutate()} disabled={saveConfig.isPending}
            className="flex items-center gap-2 px-5 py-2.5 bg-[var(--accent)] text-white rounded-lg text-sm hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-60">
            {saveConfig.isPending ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {cfgSaved ? 'Сохранено ✓' : saveConfig.isPending ? 'Сохраняем...' : 'Сохранить изменения'}
          </button>
        </div>
      )}
    </div>
  )
}
