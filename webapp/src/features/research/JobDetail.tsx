import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchJob, fetchResults, runJob, cancelJob, duplicateJob } from '../../api/research'
import { StatusBadge } from '../../shared/components/StatusBadge'
import { Play, X, Copy, Download, ArrowLeft } from 'lucide-react'

export function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: job, isLoading } = useQuery({ queryKey: ['job', id], queryFn: () => fetchJob(id!) })
  const { data: resultsData } = useQuery({ queryKey: ['results', id], queryFn: () => fetchResults(id!), enabled: !!id })

  const runMut = useMutation({ mutationFn: () => runJob(id!), onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }) })
  const cancelMut = useMutation({ mutationFn: () => cancelJob(id!), onSuccess: () => qc.invalidateQueries({ queryKey: ['job', id] }) })
  const dupMut = useMutation({ mutationFn: () => duplicateJob(id!), onSuccess: (d) => navigate(`/research/jobs/${d.id}`) })

  if (isLoading) return <div className="text-center text-[var(--text-muted)] py-12">Загрузка...</div>
  if (!job) return <div className="text-center text-[var(--error)] py-12">Задача не найдена</div>

  return (
    <div className="space-y-6">
      <button onClick={() => navigate('/research/jobs')} className="flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)]">
        <ArrowLeft size={16} /> Назад к списку
      </button>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold">{job.title}</h1>
          <div className="flex items-center gap-3 mt-2">
            <StatusBadge status={job.status} />
            <span className="text-sm text-[var(--text-muted)]">{job.job_type}</span>
            <span className="text-sm text-[var(--text-muted)]">{job.created_at?.split('T')[0]}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {['draft', 'pending', 'failed'].includes(job.status) && (
            <button onClick={() => runMut.mutate()} className="flex items-center gap-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm"><Play size={14} /> Запустить</button>
          )}
          {job.status === 'running' && (
            <button onClick={() => cancelMut.mutate()} className="flex items-center gap-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm"><X size={14} /> Отменить</button>
          )}
          <button onClick={() => dupMut.mutate()} className="flex items-center gap-1 px-3 py-1.5 bg-[var(--bg-card)] hover:bg-[var(--bg-hover)] border border-[var(--border)] rounded-lg text-sm"><Copy size={14} /> Копия</button>
        </div>
      </div>

      {job.description && (
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)]">
          <h3 className="text-sm font-medium text-[var(--text-muted)] mb-2">Описание</h3>
          <p>{job.description}</p>
        </div>
      )}

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)] flex items-center justify-between">
          <h2 className="font-semibold">Результаты ({resultsData?.total || 0})</h2>
          {resultsData?.total > 0 && (
            <a href={`/api/research/jobs/${id}/export?format=csv`} className="flex items-center gap-1 text-sm text-[var(--accent)] hover:underline"><Download size={14} /> CSV</a>
          )}
        </div>
        <div className="divide-y divide-[var(--border)]">
          {resultsData?.items?.map((r: any) => (
            <div key={r.id} className="p-4">
              <div className="font-medium">{r.title || 'Без заголовка'}</div>
              {r.source_url && <a href={r.source_url} target="_blank" rel="noreferrer" className="text-sm text-[var(--accent)] hover:underline">{r.source_url}</a>}
              {r.extracted_fields && (
                <div className="mt-2 text-sm text-[var(--text-secondary)] grid grid-cols-2 gap-1">
                  {Object.entries(r.extracted_fields).map(([k, v]) => (
                    <div key={k}><span className="text-[var(--text-muted)]">{k}:</span> {String(v).slice(0, 80)}</div>
                  ))}
                </div>
              )}
            </div>
          )) || <div className="p-8 text-center text-[var(--text-muted)]">Нет результатов</div>}
        </div>
      </div>
    </div>
  )
}
