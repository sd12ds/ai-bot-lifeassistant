import { useQuery } from "@tanstack/react-query"
import { fetchSources } from "../../../api/research"

export function SourcesList({ jobId }: { jobId: string }) {
  const { data: sources } = useQuery({ queryKey: ["sources", jobId], queryFn: () => fetchSources(jobId) })
  if (!sources?.length) return <p className="text-sm text-[var(--text-muted)]">Нет источников</p>
  return (
    <div className="space-y-1">
      {sources.map((s: any) => (
        <div key={s.id} className="flex items-center gap-2 text-sm">
          <span className="px-1.5 py-0.5 rounded text-xs bg-[var(--bg-hover)] text-[var(--text-muted)]">{s.source_type}</span>
          <a href={s.url} target="_blank" rel="noreferrer" className="text-[var(--accent)] hover:underline truncate">{s.url}</a>
          <span className="text-[var(--text-muted)]">{s.status}</span>
        </div>
      ))}
    </div>
  )
}
