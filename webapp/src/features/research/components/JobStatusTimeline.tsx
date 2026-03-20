export function JobStatusTimeline({ status }: { status: string }) {
  const steps = ["draft", "pending", "running", "completed"]
  const current = steps.indexOf(status)
  return (
    <div className="flex items-center gap-1">
      {steps.map((step, i) => (
        <div key={step} className="flex items-center gap-1">
          <div className={`w-2.5 h-2.5 rounded-full ${i <= current ? "bg-[var(--accent)]" : i === current + 1 && status === "running" ? "bg-blue-400 animate-pulse" : "bg-[var(--border)]"}`} />
          <span className={`text-xs ${i <= current ? "text-[var(--text-primary)]" : "text-[var(--text-muted)]"}`}>{step}</span>
          {i < steps.length - 1 && <div className={`w-6 h-0.5 ${i < current ? "bg-[var(--accent)]" : "bg-[var(--border)]"}`} />}
        </div>
      ))}
      {status === "failed" && <span className="ml-2 text-xs text-[var(--error)]">failed</span>}
    </div>
  )
}
