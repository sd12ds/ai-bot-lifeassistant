/** ParseRunCard — карточка запуска парсинга: статус, время, найдено/новых. */
import { CheckCircle, XCircle, Loader2, Clock } from 'lucide-react'
import type { ParseRun } from '../../../../api/social'

interface Props { run: ParseRun }

function formatDuration(start: string | null, end: string | null): string {
  if (!start || !end) return ''
  const s = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
  if (s < 60) return `${s}с`
  return `${Math.floor(s / 60)}м ${s % 60}с`
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('ru-RU', {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
  })
}

export function ParseRunCard({ run }: Props) {
  const statusMap = {
    completed: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-900/20', label: 'Завершён' },
    failed:    { icon: XCircle,     color: 'text-red-400',   bg: 'bg-red-900/20',   label: 'Ошибка' },
    running:   { icon: Loader2,     color: 'text-blue-400',  bg: 'bg-blue-900/20',  label: 'Запущен' },
  }
  const cfg = statusMap[run.status as keyof typeof statusMap] ?? statusMap.running
  const Icon = cfg.icon

  return (
    <div className={`rounded-xl p-3 border border-[var(--border)] ${cfg.bg}`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Icon size={14} className={`${cfg.color} ${run.status === 'running' ? 'animate-spin' : ''}`} />
          <span className={`text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
        </div>
        <span className="text-xs text-[var(--text-muted)]">{formatDate(run.started_at)}</span>
      </div>
      <div className="flex items-center gap-3 text-xs text-[var(--text-secondary)]">
        <span>Найдено: {run.posts_found}</span>
        <span className="text-green-400">Новых: +{run.posts_new}</span>
        {run.started_at && run.finished_at && (
          <span className="flex items-center gap-1"><Clock size={10} />{formatDuration(run.started_at, run.finished_at)}</span>
        )}
      </div>
      {run.error_details && (
        <p className="text-xs text-red-400 mt-1 truncate" title={run.error_details}>{run.error_details}</p>
      )}
    </div>
  )
}
