/** SparklineChart — мини-график постов за 7 дней через recharts. */
import { ResponsiveContainer, AreaChart, Area, Tooltip } from 'recharts'

interface Props {
  data: Array<{ day: string; count: number }>
  color?: string
}

export function SparklineChart({ data, color = '#818cf8' }: Props) {
  if (!data || data.length === 0) {
    return <div className="h-8 flex items-center justify-center text-xs text-[var(--text-muted)]">нет данных</div>
  }
  const gradId = `sg${color.replace(/[#]/g, '')}`
  return (
    <ResponsiveContainer width="100%" height={32}>
      <AreaChart data={data} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity={0.3} />
            <stop offset="95%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Tooltip
          contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 11 }}
        />
        <Area
          type="monotone"
          dataKey="count"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#${gradId})`}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
