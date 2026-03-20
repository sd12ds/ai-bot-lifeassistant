import { Download } from "lucide-react"

export function ExportButton({ jobId }: { jobId: string }) {
  return (
    <a href={`/api/research/jobs/${jobId}/export?format=csv`} download
      className="flex items-center gap-1 px-3 py-1.5 bg-[var(--bg-card)] hover:bg-[var(--bg-hover)] border border-[var(--border)] rounded-lg text-sm">
      <Download size={14} /> CSV
    </a>
  )
}
