import { useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { fetchResults, fetchJob } from "../../api/research"
import { ExportButton } from "./components/ExportButton"

export function ResultsExplorer() {
  const { id } = useParams<{ id: string }>()
  const { data: job } = useQuery({ queryKey: ["job", id], queryFn: () => fetchJob(id!) })
  const { data } = useQuery({ queryKey: ["results", id], queryFn: () => fetchResults(id!, { limit: 200 }) })
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Результаты: {job?.title || "..."}</h1>
        {id && <ExportButton jobId={id} />}
      </div>
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-secondary)]">
            <tr>
              <th className="text-left p-3 font-medium text-[var(--text-muted)]">Название</th>
              <th className="text-left p-3 font-medium text-[var(--text-muted)]">Домен</th>
              <th className="text-left p-3 font-medium text-[var(--text-muted)]">URL</th>
              <th className="text-left p-3 font-medium text-[var(--text-muted)]">Данные</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {data?.items?.map((r: any) => (
              <tr key={r.id} className="hover:bg-[var(--bg-hover)]">
                <td className="p-3 font-medium">{r.title || "-"}</td>
                <td className="p-3 text-[var(--text-muted)]">{r.domain || "-"}</td>
                <td className="p-3"><a href={r.source_url} target="_blank" rel="noreferrer" className="text-[var(--accent)] hover:underline truncate block max-w-xs">{r.source_url}</a></td>
                <td className="p-3 text-[var(--text-muted)] text-xs">{r.extracted_fields ? Object.keys(r.extracted_fields).join(", ") : "-"}</td>
              </tr>
            )) || <tr><td colSpan={4} className="p-8 text-center text-[var(--text-muted)]">Нет результатов</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="text-sm text-[var(--text-muted)]">Всего: {data?.total || 0}</div>
    </div>
  )
}
