import { useQuery } from '@tanstack/react-query'
import { fetchJobs } from '../../api/research'
import { StatusBadge } from '../../shared/components/StatusBadge'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'

const STATUSES = ['', 'draft', 'pending', 'running', 'completed', 'failed', 'canceled']

export function JobsList() {
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState('')
  const { data: jobs, isLoading } = useQuery({
    queryKey: ['jobs', statusFilter],
    queryFn: () => fetchJobs({ status: statusFilter || undefined, limit: 50 }),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Задачи сбора</h1>
        <div className="flex gap-2">
          {STATUSES.map(s => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors
                ${statusFilter === s ? 'bg-[var(--accent)] text-white' : 'bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'}`}>
              {s || 'Все'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-[var(--text-muted)] py-12">Загрузка...</div>
      ) : !jobs?.length ? (
        <div className="text-center text-[var(--text-muted)] py-12 bg-[var(--bg-card)] rounded-xl border border-[var(--border)]">
          Нет задач{statusFilter ? ` со статусом "${statusFilter}"` : ''}
        </div>
      ) : (
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--bg-secondary)]">
              <tr>
                <th className="text-left p-3 font-medium text-[var(--text-muted)]">Название</th>
                <th className="text-left p-3 font-medium text-[var(--text-muted)]">Тип</th>
                <th className="text-left p-3 font-medium text-[var(--text-muted)]">Статус</th>
                <th className="text-left p-3 font-medium text-[var(--text-muted)]">Дата</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {jobs.map((job: any) => (
                <tr key={job.id} onClick={() => navigate(`/research/jobs/${job.id}`)}
                  className="cursor-pointer hover:bg-[var(--bg-hover)] transition-colors">
                  <td className="p-3 font-medium">{job.title}</td>
                  <td className="p-3 text-[var(--text-muted)]">{job.job_type}</td>
                  <td className="p-3"><StatusBadge status={job.status} /></td>
                  <td className="p-3 text-[var(--text-muted)]">{job.created_at?.split('T')[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
