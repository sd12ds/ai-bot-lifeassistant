/** SourceCard — карточка источника мониторинга с sparkline и кнопками действий. */
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Pause, RotateCw } from 'lucide-react'
import type { SocialSource } from '../../../../api/social'
import { updateSource, triggerParse } from '../../../../api/social'
import { PlatformIcon, PlatformBadge } from './PlatformBadge'
import { CollectionTypeBadge } from './ContentTypeFilter'
import { SourceStatusBadge } from './SourceStatusBadge'
import { SparklineChart } from './SparklineChart'

interface Props { source: SocialSource; sparkData?: Array<{ day: string; count: number }> }

function formatRelative(iso: string | null): string {
  if (!iso) return 'никогда'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60)   return 'только что'
  if (diff < 3600) return `${Math.floor(diff / 60)}м назад`
  if (diff < 86400) return `${Math.floor(diff / 3600)}ч назад`
  return `${Math.floor(diff / 86400)}д назад`
}

function formatNext(schedule: Record<string, any> | null, lastParsed: string | null): string {
  if (!schedule || !lastParsed) return 'скоро'
  const hours = schedule.interval_hours ?? 6
  const next = new Date(new Date(lastParsed).getTime() + hours * 3600000)
  const diff = (next.getTime() - Date.now()) / 1000
  if (diff <= 0) return 'сейчас'
  if (diff < 3600) return `через ${Math.floor(diff / 60)}м`
  if (diff < 86400) return `через ${Math.floor(diff / 3600)}ч`
  return `через ${Math.floor(diff / 86400)}д`
}

export function SourceCard({ source, sparkData }: Props) {
  const navigate = useNavigate()
  const qc = useQueryClient()

  const toggleStatus = useMutation({
    mutationFn: () => updateSource(source.id, {
      status: source.status === 'active' ? 'paused' : 'active'
    } as any),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['social-sources'] }),
  })

  const parse = useMutation({
    mutationFn: () => triggerParse(source.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['social-sources'] }),
  })

  // Используем реальные sparkline-данные, переданные из родителя
  const chartData = sparkData ?? []

  const subs = source.source_meta?.subscribers_count
  const subsLabel = subs ? (subs >= 1000 ? `${(subs / 1000).toFixed(1)}K` : subs) : null

  return (
    <div
      className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-4 flex flex-col gap-3 cursor-pointer hover:border-[var(--accent)]/40 transition-colors"
      onClick={e => { if ((e.target as HTMLElement).closest('button')) return; navigate(`/research/social/${source.id}`) }}
    >
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <PlatformIcon platform={source.platform} size={16} />
          <span className="font-medium text-sm truncate">{source.source_name || source.source_id}</span>
        </div>
        <SourceStatusBadge status={source.status} />
      </div>

      {/* Подзаголовок */}
      <div className="flex items-center gap-2 flex-wrap">
        <PlatformBadge platform={source.platform} showLabel={true} size="sm" />
        {source.collection_config?.results_type && (
          <CollectionTypeBadge resultsType={source.collection_config.results_type} />
        )}
        {subsLabel && <span className="text-xs text-[var(--text-muted)]">{subsLabel} подписчиков</span>}
      </div>

      {/* Sparkline */}
      <div>
        <SparklineChart data={chartData} />
        <p className="text-xs text-[var(--text-muted)] mt-1">
          посты за 7 дней
        </p>
      </div>

      {/* Тайминги */}
      <div className="space-y-0.5 text-xs text-[var(--text-secondary)]">
        <div>⏰ Последний: {formatRelative(source.last_parsed_at)}</div>
        <div>⏭ Следующий: {formatNext(source.schedule, source.last_parsed_at)}</div>
        {source.last_error && (
          <div className="text-red-400 truncate" title={source.last_error}>⚠ {source.last_error}</div>
        )}
      </div>

      {/* Кнопки */}
      <div className="flex gap-2 pt-1 border-t border-[var(--border)]">
        <button
          onClick={e => { e.stopPropagation(); toggleStatus.mutate() }}
          disabled={toggleStatus.isPending}
          className="flex-1 flex items-center justify-center gap-1 py-1.5 text-xs rounded-lg border border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] transition-colors"
        >
          {source.status === 'active' ? <><Pause size={12} /> Пауза</> : <><Play size={12} /> Возобновить</>}
        </button>
        <button
          onClick={e => { e.stopPropagation(); parse.mutate() }}
          disabled={parse.isPending}
          className="flex-1 flex items-center justify-center gap-1 py-1.5 text-xs rounded-lg border border-[var(--accent)]/40 text-[var(--accent)] hover:bg-[var(--accent)]/10 transition-colors"
        >
          <RotateCw size={12} className={parse.isPending ? 'animate-spin' : ''} />
          {parse.isPending ? 'Запуск...' : 'Запустить'}
        </button>
      </div>
    </div>
  )
}
