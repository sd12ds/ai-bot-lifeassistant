import { useQuery } from "@tanstack/react-query"
import { fetchRuns } from "../../../api/research"

export function RunLogPanel({ jobId }: { jobId: string }) {
  const { data: runs } = useQuery({ queryKey: ["runs", jobId], queryFn: () => fetchRuns(jobId) })
  if (!runs?.length) return <p className="text-sm text-[var(--text-muted)]">Нет запусков</p>
  return (
    <div className="space-y-2">
      {runs.map((r: any) => (
        <div key={r.id} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border)] text-sm">
          <div className="flex justify-between"><span className="font-medium">{r.status}</span><span className="text-[var(--text-muted)]">{r.started_at?.split("T")[0]}</span></div>
          {r.metrics && <div className="text-[var(--text-muted)] mt-1">{JSON.stringify(r.metrics)}</div>}
          {r.error_details && <div className="text-[var(--error)] mt-1">{r.error_details}</div>}
        </div>
      ))}
    </div>
  )
}
