/**
 * Трекер воды — стаканы + кнопка быстрого добавления.
 */
import { motion } from 'framer-motion'
import { Droplets, Plus } from 'lucide-react'

interface WaterTrackerProps {
  current: number
  goal: number
  onAdd: (ml: number) => void
  loading?: boolean
}

export function WaterTracker({ current, goal, onAdd, loading }: WaterTrackerProps) {
  // Количество стаканов (по 250мл) — макс 8
  const glassSize = 250
  const totalGlasses = Math.ceil(goal / glassSize)
  const filledGlasses = Math.floor(current / glassSize)

  return (
    <div className="flex flex-col gap-2">
      {/* Заголовок */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-1.5">
          <Droplets size={14} style={{ color: '#38bdf8' }} />
          <span className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>Вода</span>
        </div>
        <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
          {current} / {goal} мл
        </span>
      </div>

      {/* Стаканы */}
      <div className="flex items-center gap-1 flex-wrap">
        {Array.from({ length: Math.min(totalGlasses, 8) }).map((_, i) => (
          <motion.div
            key={i}
            className="w-6 h-8 rounded-md border"
            style={{
              borderColor: i < filledGlasses ? '#38bdf8' : 'rgba(255,255,255,0.1)',
              background: i < filledGlasses ? 'rgba(56,189,248,0.2)' : 'transparent',
            }}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: i * 0.03 }}
          />
        ))}

        {/* Кнопка +250мл */}
        <motion.button
          onClick={() => onAdd(glassSize)}
          disabled={loading}
          className="w-8 h-8 rounded-full flex items-center justify-center ml-1"
          style={{ background: 'rgba(56,189,248,0.15)', border: '1px solid rgba(56,189,248,0.3)' }}
          whileTap={{ scale: 0.9 }}
        >
          <Plus size={14} style={{ color: '#38bdf8' }} />
        </motion.button>
      </div>
    </div>
  )
}
