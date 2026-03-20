import { useQuery } from "@tanstack/react-query"
import { fetchUsage } from "../../api/billing"

export function QuotaIndicator() {
  const { data } = useQuery({ queryKey: ["usage"], queryFn: fetchUsage, refetchInterval: 60000 })
  if (!data?.metrics || Object.keys(data.metrics).length === 0) return null
  const entries = Object.entries(data.metrics) as [string, any][]
  const worst = entries.reduce((a, b) => {
    const pctA = a[1].limit > 0 ? a[1].consumed / a[1].limit : 0
    const pctB = b[1].limit > 0 ? b[1].consumed / b[1].limit : 0
    return pctA > pctB ? a : b
  })
  const pct = worst[1].limit > 0 ? Math.round((worst[1].consumed / worst[1].limit) * 100) : 0
  if (pct < 50) return null
  return (
    <div className={`px-2 py-1 rounded text-xs font-medium ${pct >= 90 ? "bg-red-900/30 text-[var(--error)]" : "bg-yellow-900/30 text-[var(--warning)]"}`}>
      {worst[0]}: {pct}%
    </div>
  )
}
