/**
 * Кольцевая диаграмма потребления калорий.
 * SVG ring с анимацией через framer-motion.
 */
import { motion } from 'framer-motion'

interface CalorieRingProps {
  consumed: number
  goal: number
}

export function CalorieRing({ consumed, goal }: CalorieRingProps) {
  // Расчёт прогресса (0..1, макс 1.0 для визуала)
  const progress = goal > 0 ? Math.min(consumed / goal, 1) : 0
  const remaining = Math.max(goal - consumed, 0)

  // SVG параметры кольца
  const size = 140
  const stroke = 10
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius

  // Цвет: зелёный → жёлтый → красный
  const color =
    progress < 0.7 ? '#22c55e' : progress < 0.9 ? '#eab308' : '#ef4444'

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size }}>
        {/* Фоновое кольцо */}
        <svg width={size} height={size} className="absolute inset-0">
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={stroke}
          />
        </svg>
        {/* Прогресс */}
        <svg width={size} height={size} className="absolute inset-0 -rotate-90">
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference * (1 - progress) }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          />
        </svg>
        {/* Центральный текст */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
            {Math.round(consumed)}
          </span>
          <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
            из {goal} ккал
          </span>
        </div>
      </div>
      {/* Осталось */}
      <p className="text-xs mt-2" style={{ color: 'var(--app-hint)' }}>
        Осталось: {Math.round(remaining)} ккал
      </p>
    </div>
  )
}
