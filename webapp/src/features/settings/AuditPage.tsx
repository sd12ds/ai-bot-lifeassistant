import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'

const fetchAuditEvents = () => api.get('/audit/events').then(r => r.data).catch(() => ({ items: [], message: "Audit events coming in Phase 4+" }))

export function AuditPage() {
  const { data } = useQuery({ queryKey: ['audit'], queryFn: fetchAuditEvents })

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Audit & Security</h1>
      <div className="bg-[var(--bg-card)] rounded-xl p-6 border border-[var(--border)]">
        <p className="text-[var(--text-muted)]">{data?.message || 'Audit log viewer'}</p>
        {data?.items?.length > 0 && (
          <div className="mt-4 space-y-2">
            {data.items.map((e: any) => (
              <div key={e.id} className="text-sm p-2 bg-[var(--bg-primary)] rounded border border-[var(--border)]">
                <span className="text-[var(--accent)]">{e.action}</span>
                <span className="text-[var(--text-muted)] ml-2">{e.created_at}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
