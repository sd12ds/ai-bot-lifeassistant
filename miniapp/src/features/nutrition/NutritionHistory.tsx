/**
 * Страница статистики — bar-chart калорий + средние за период.
 * SVG + framer-motion (без recharts).
 */
import { useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useNutritionStats } from '../../api/nutrition'
import { GlassCard } from '../../shared/ui/GlassCard'

export function NutritionHistory() {
  const navigate = useNavigate()
  const [period, setPeriod] = useState<'week' | 'month'>('week')
  const { data: stats, isLoading } = useNutritionStats(period)

  // Параметры SVG
  const chartH = 160
  const barWidth = period === 'week' ? 28 : 8
  const gap = period === 'week' ? 8 : 3

  // Данные для отображения (от старых к новым)
  const daily = stats?.daily ? [...stats.daily].reverse() : []
  const maxCal = Math.max(...daily.map((d) => d.totals.calories), stats?.avg_calories ?? 2000) * 1.1

  const chartW = daily.length * (barWidth + gap)
  const goalY = stats?.avg_calories ? chartH - (stats.avg_calories / maxCal) * chartH : 0

  return (
    <div className="flex flex-col h-full overflow-y-auto pb-24 px-4 pt-4">
      {/* Шапка */}
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => navigate('/nutrition')}>
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>Статистика</h1>
      </div>

      {/* Переключатель периода */}
      <div className="flex gap-2 mb-4">
        {(['week', 'month'] as const).map((p) => (
          <button
            key={p}
            onClick={() => setPeriod(p)}
            className="flex-1 py-2 rounded-xl text-xs font-medium border"
            style={{
              borderColor: period === p ? '#818cf8' : 'rgba(255,255,255,0.08)',
              background: period === p ? 'rgba(99,102,241,0.15)' : 'transparent',
              color: period === p ? '#818cf8' : 'var(--app-hint)',
            }}
          >
            {p === 'week' ? 'Неделя' : 'Месяц'}
          </button>
        ))}
      </div>

      {/* Средние */}
      {stats && (
        <GlassCard className="mb-4">
          <div className="grid grid-cols-2 gap-2 text-center">
            <div>
              <p className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>{Math.round(stats.avg_calories)}</p>
              <p className="text-[10px]" style={{ color: 'var(--app-hint)' }}>ср. ккал/день</p>
            </div>
            <div>
              <p className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>{Math.round(stats.avg_water)}</p>
              <p className="text-[10px]" style={{ color: 'var(--app-hint)' }}>ср. вода мл</p>
            </div>
          </div>
        </GlassCard>
      )}

      {/* Bar chart */}
      {isLoading ? (
        <div className="h-40 flex items-center justify-center">
          <p className="text-xs" style={{ color: 'var(--app-hint)' }}>Загрузка...</p>
        </div>
      ) : (
        <GlassCard noPadding className="p-3 overflow-x-auto">
          <svg width={Math.max(chartW, 280)} height={chartH + 20} className="mx-auto">
            {/* Линия средней цели */}
            <line
              x1={0} y1={goalY} x2={chartW} y2={goalY}
              stroke="#818cf8" strokeWidth={1} strokeDasharray="4 4" opacity={0.5}
            />
            {/* Бары */}
            {daily.map((d, i) => {
              const h = maxCal > 0 ? (d.totals.calories / maxCal) * chartH : 0
              const x = i * (barWidth + gap)
              return (
                <g key={d.date}>
                  <motion.rect
                    x={x} y={chartH - h} width={barWidth} height={h}
                    rx={barWidth / 4}
                    fill="#6366f1"
                    initial={{ height: 0, y: chartH }}
                    animate={{ height: h, y: chartH - h }}
                    transition={{ duration: 0.4, delay: i * 0.03 }}
                  />
                  {/* Дата внизу */}
                  <text
                    x={x + barWidth / 2}
                    y={chartH + 14}
                    textAnchor="middle"
                    fill="var(--app-hint)"
                    fontSize={period === 'week' ? 9 : 7}
                  >
                    {d.date.slice(8)}
                  </text>
                </g>
              )
            })}
          </svg>
        </GlassCard>
      )}
    </div>
  )
}
