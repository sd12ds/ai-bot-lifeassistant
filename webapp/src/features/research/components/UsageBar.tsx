export function UsageBar({ consumed, limit, label }: { consumed: number; limit: number; label: string }) {
  const pct = limit > 0 ? Math.min(100, (consumed / limit) * 100) : 0
  const color = pct >= 90 ? "bg-[var(--error)]" : pct >= 70 ? "bg-[var(--warning)]" : "bg-[var(--accent)]"
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs"><span className="text-[var(--text-muted)]">{label}</span><span>{consumed} / {limit}</span></div>
      <div className="w-full h-1.5 bg-[var(--border)] rounded-full"><div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} /></div>
    </div>
  )
}
