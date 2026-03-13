/**
 * Горизонтальные pill-табы для фильтрации задач.
 * Активный таб подсвечивается animated indicator (Framer Motion layoutId).
 */
import { motion } from 'framer-motion'
import type { TaskPeriod } from '../../api/tasks'

interface FilterTab {
  key: TaskPeriod
  label: string
  emoji: string
}

const TABS: FilterTab[] = [
  { key: 'all',    label: 'Все',      emoji: '📋' },
  { key: 'today',  label: 'Сегодня',  emoji: '☀️' },
  { key: 'week',   label: 'Неделя',   emoji: '📅' },
  { key: 'nodate', label: 'Без срока',emoji: '∞'  },
]

interface FilterTabsProps {
  active: TaskPeriod
  onChange: (period: TaskPeriod) => void
}

export function FilterTabs({ active, onChange }: FilterTabsProps) {
  return (
    <div className="px-4 py-2">
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {TABS.map((tab) => {
          const isActive = active === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => onChange(tab.key)}
              className="relative flex-shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-[999px] text-sm font-medium transition-colors"
              style={{
                color: isActive ? '#fff' : 'var(--app-hint)',
                border: isActive ? 'none' : '1px solid rgba(255,255,255,0.08)',
                background: isActive ? 'transparent' : 'var(--glass-bg)',
              }}
            >
              {/* Анимированный фон активного таба */}
              {isActive && (
                <motion.div
                  layoutId="filter-active"
                  className="absolute inset-0 rounded-[999px] gradient-bg"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}
              <span className="relative z-10">{tab.emoji}</span>
              <span className="relative z-10">{tab.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
