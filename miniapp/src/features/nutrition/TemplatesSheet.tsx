/**
 * Нижний лист управления шаблонами приёмов пищи.
 * Список шаблонов, кнопки «Применить» и «Удалить».
 */
import { motion, AnimatePresence } from 'framer-motion'
import { X, Play, Trash2, UtensilsCrossed } from 'lucide-react'
import { useTemplates, useApplyTemplate, useDeleteTemplate } from '../../api/nutrition'

interface TemplatesSheetProps {
  open: boolean
  onClose: () => void
}

const MEAL_LABELS: Record<string, string> = {
  breakfast: '🌅 Завтрак',
  lunch: '☀️ Обед',
  dinner: '🌙 Ужин',
  snack: '🍎 Перекус',
}

export function TemplatesSheet({ open, onClose }: TemplatesSheetProps) {
  const { data: templates, isLoading } = useTemplates()
  const applyTemplate = useApplyTemplate()
  const deleteTemplate = useDeleteTemplate()

  // Применить шаблон и закрыть
  const handleApply = (id: number) => {
    applyTemplate.mutate(id, { onSuccess: onClose })
  }

  // Удалить шаблон с подтверждением
  const handleDelete = (id: number, name: string) => {
    if (confirm(`Удалить шаблон «${name}»?`)) {
      deleteTemplate.mutate(id)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Затемнение */}
          <motion.div
            className="fixed inset-0"
            style={{ background: 'rgba(0,0,0,0.5)', zIndex: 50 }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          {/* Лист */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 rounded-t-[24px] p-4 pb-8 max-h-[75vh] overflow-y-auto"
            style={{ background: 'var(--app-bg)', zIndex: 51, borderTop: '1px solid rgba(255,255,255,0.08)' }}
            initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {/* Заголовок */}
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>📋 Шаблоны</h2>
              <button onClick={onClose}><X size={20} style={{ color: 'var(--app-hint)' }} /></button>
            </div>

            {/* Загрузка */}
            {isLoading && (
              <p className="text-xs text-center py-4" style={{ color: 'var(--app-hint)' }}>Загрузка...</p>
            )}

            {/* Пустой список */}
            {templates && templates.length === 0 && (
              <div className="text-center py-8">
                <UtensilsCrossed size={32} className="mx-auto mb-2" style={{ color: 'var(--app-hint)' }} />
                <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
                  Шаблонов пока нет. Сохраните приём пищи как шаблон через меню блюда.
                </p>
              </div>
            )}

            {/* Список шаблонов */}
            <div className="flex flex-col gap-2">
              {templates?.map((tmpl) => (
                <div
                  key={tmpl.id}
                  className="p-3 rounded-xl border border-white/[0.08]"
                  style={{ background: 'rgba(255,255,255,0.02)' }}
                >
                  <div className="flex justify-between items-start mb-1.5">
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>{tmpl.name}</p>
                      <p className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                        {MEAL_LABELS[tmpl.meal_type] || tmpl.meal_type} · {Math.round(tmpl.total_calories)} ккал
                      </p>
                    </div>
                    <div className="flex gap-1.5">
                      {/* Применить */}
                      <motion.button
                        onClick={() => handleApply(tmpl.id)}
                        disabled={applyTemplate.isPending}
                        className="px-3 py-1.5 rounded-lg text-[11px] font-medium text-white flex items-center gap-1"
                        style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
                        whileTap={{ scale: 0.95 }}
                      >
                        <Play size={10} /> Применить
                      </motion.button>
                      {/* Удалить */}
                      <button
                        onClick={() => handleDelete(tmpl.id, tmpl.name)}
                        className="p-1.5 rounded-lg"
                        style={{ background: 'rgba(239,68,68,0.1)' }}
                      >
                        <Trash2 size={12} style={{ color: '#ef4444' }} />
                      </button>
                    </div>
                  </div>
                  {/* Позиции шаблона */}
                  <div className="flex flex-wrap gap-1">
                    {tmpl.items.map((item) => (
                      <span
                        key={item.id}
                        className="px-2 py-0.5 rounded text-[10px]"
                        style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
                      >
                        {item.name} {item.amount_g}г
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
