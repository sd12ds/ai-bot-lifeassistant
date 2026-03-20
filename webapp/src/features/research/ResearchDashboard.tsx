import { useQuery } from '@tanstack/react-query'
import { fetchStats, fetchJobs } from '../../api/research'
import { StatusBadge } from '../../shared/components/StatusBadge'
import { useNavigate } from 'react-router-dom'
import { Plus, Activity, CheckCircle, XCircle, FileText } from 'lucide-react'

export function ResearchDashboard() {
  const navigate = useNavigate()
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: fetchStats })
  const { data: recentJobs } = useQuery({ queryKey: ['jobs', 'recent'], queryFn: () => fetchJobs({ limit: 5 }) })

  const widgets = [
    { label: 'Всего задач', value: stats?.total_jobs || 0, icon: FileText, color: 'text-[var(--accent)]' },
    { label: 'Активных', value: stats?.running || 0, icon: Activity, color: 'text-blue-400' },
    { label: 'Завершено', value: stats?.completed || 0, icon: CheckCircle, color: 'text-green-400' },
    { label: 'С ошибками', value: stats?.failed || 0, icon: XCircle, color: 'text-red-400' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <button onClick={() => navigate('/research/jobs/new')}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-lg text-sm font-medium transition-colors">
          <Plus size={16} /> Новая задача
        </button>
      </div>

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

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-semibold">Последние задачи</h2>
        </div>
        <div className="divide-y divide-[var(--border)]">
          {recentJobs?.map((job: any) => (
            <div key={job.id} onClick={() => navigate(`/research/jobs/${job.id}`)}
              className="p-4 flex items-center justify-between cursor-pointer hover:bg-[var(--bg-hover)] transition-colors">
              <div>
                <div className="font-medium">{job.title}</div>
                <div className="text-sm text-[var(--text-muted)]">{job.job_type} · {job.created_at?.split('T')[0]}</div>
              </div>
              <StatusBadge status={job.status} />
            </div>
          )) || <div className="p-8 text-center text-[var(--text-muted)]">Нет задач. Создайте первую!</div>}
        </div>
      </div>
    </div>
  )
}
