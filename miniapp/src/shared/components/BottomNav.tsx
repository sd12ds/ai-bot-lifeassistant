/**
 * Нижняя плавающая навигационная панель.
 * Floating nav с blur-фоном, активный пункт — градиентный pill.
 */
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CheckSquare, CalendarDays, Utensils, Dumbbell, Target } from 'lucide-react'

interface NavItem {
  path: string
  icon: typeof CheckSquare
  label: string
  enabled: boolean
}

const NAV_ITEMS: NavItem[] = [
  { path: '/tasks',    icon: CheckSquare, label: 'Задачи',     enabled: true },
  { path: '/calendar', icon: CalendarDays, label: 'Календарь',  enabled: true },
  { path: '/nutrition',icon: Utensils,    label: 'Питание',    enabled: true },
  { path: '/fitness',  icon: Dumbbell,    label: 'Фитнес',     enabled: true },
  { path: '/coaching', icon: Target,      label: 'Коучинг',    enabled: true  },
]

export function BottomNav() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div
      className="fixed bottom-0 left-0 right-0 px-4 pb-4 pt-2"
      style={{ zIndex: 50 }}
    >
      <nav
        className="flex items-center justify-around rounded-[24px] px-2 py-2 backdrop-blur-2xl border border-white/[0.08]"
        style={{
          background: 'rgba(15, 15, 26, 0.85)',
          boxShadow: 'var(--shadow-nav)',
        }}
      >
        {NAV_ITEMS.map((item) => {
          const isActive = location.pathname.startsWith(item.path)
          const Icon = item.icon

          return (
            <button
              key={item.path}
              onClick={() => item.enabled && navigate(item.path)}
              className="relative flex flex-col items-center justify-center flex-1 py-1 rounded-[16px] transition-opacity"
              style={{ opacity: item.enabled ? 1 : 0.35 }}
              disabled={!item.enabled}
            >
              {/* Активный индикатор — градиентная подсветка */}
              {isActive && (
                <motion.div
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-[16px]"
                  style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.25), rgba(139,92,246,0.15))' }}
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                />
              )}
              <Icon
                size={22}
                className="relative z-10"
                style={{ color: isActive ? '#818cf8' : 'var(--app-hint)' }}
              />
              <span
                className="relative z-10 text-[10px] font-medium mt-0.5"
                style={{ color: isActive ? '#818cf8' : 'var(--app-hint)' }}
              >
                {item.label}
              </span>
            </button>
          )
        })}
      </nav>
    </div>
  )
}
