/**
 * Карточка приёма пищи — тип, время, продукты, итого ккал.
 * Разворачивается для деталей, кнопка удаления.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, Trash2, Bookmark } from 'lucide-react'
import type { Meal } from '../../api/nutrition'
import { GlassCard } from '../../shared/ui/GlassCard'

interface MealCardProps {
  meal: Meal
  onDelete?: (id: number) => void
  onEdit?: (id: number) => void
  onSaveAsTemplate?: (id: number) => void
}

/** Иконка и название типа приёма пищи */
const MEAL_TYPE_MAP: Record<string, { icon: string; label: string }> = {
  breakfast: { icon: '🌅', label: 'Завтрак' },
  lunch:     { icon: '☀️', label: 'Обед' },
  dinner:    { icon: '🌙', label: 'Ужин' },
  snack:     { icon: '🍎', label: 'Перекус' },
}

/** Форматирует время из ISO-строки */
function formatTime(iso: string | null): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

export function MealCard({ meal, onDelete, onEdit, onSaveAsTemplate }: MealCardProps) {
  const [expanded, setExpanded] = useState(false)
  const meta = MEAL_TYPE_MAP[meal.meal_type] ?? { icon: '🍽', label: meal.meal_type }

  return (
    <GlassCard className="overflow-hidden">
      {/* Шапка — тап для раскрытия */}
      <button
        className="w-full flex items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-lg">{meta.icon}</span>
          <div className="text-left">
            <p className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              {meta.label}
            </p>
            <p className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
              {formatTime(meal.eaten_at)} · {meal.items.length} продукт.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
            {Math.round(meal.total_calories)} ккал
          </span>
          <motion.div animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
            <ChevronDown size={16} style={{ color: 'var(--app-hint)' }} />
          </motion.div>
        </div>
      </button>

      {/* Детали — раскрываемый блок */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-3 pt-3 border-t border-white/[0.06] flex flex-col gap-2">
              {meal.items.map((item) => (
                <div key={item.id} className="flex justify-between text-xs">
                  <div>
                    <span style={{ color: 'var(--app-text)' }}>{item.name}</span>
                    <span className="ml-1" style={{ color: 'var(--app-hint)' }}>
                      {item.amount_g}г
                    </span>
                  </div>
                  <span style={{ color: 'var(--app-hint)' }}>
                    {Math.round(item.calories)} · Б{Math.round(item.protein_g)} Ж{Math.round(item.fat_g)} У{Math.round(item.carbs_g)}
                  </span>
                </div>
              ))}
              {/* Кнопки действий */}
              <div className="flex justify-end gap-2 mt-1">
                {onSaveAsTemplate && (
                  <button
                    onClick={() => onSaveAsTemplate(meal.id)}
                    className="text-xs px-2 py-1 rounded-lg flex items-center gap-1"
                    style={{ color: '#f59e0b', background: 'rgba(245,158,11,0.1)' }}
                  >
                    <Bookmark size={10} /> Шаблон
                  </button>
                )}
                {onEdit && (
                  <button
                    onClick={() => onEdit(meal.id)}
                    className="text-xs px-3 py-1 rounded-lg"
                    style={{ color: '#818cf8', background: 'rgba(99,102,241,0.1)' }}
                  >
                    Изменить
                  </button>
                )}
                {onDelete && (
                  <button
                    onClick={() => onDelete(meal.id)}
                    className="p-1 rounded-lg"
                    style={{ color: '#ef4444', background: 'rgba(239,68,68,0.1)' }}
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </GlassCard>
  )
}
