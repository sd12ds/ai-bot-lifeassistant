/**
 * Нижний лист редактирования приёма пищи.
 * Загружает существующий meal, позволяет менять граммовку, удалять/добавлять продукты.
 */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Minus, Plus, Loader2 } from 'lucide-react'
import { fetchMeal, useUpdateMeal, type MealItemCreate, type FoodItem } from '../../api/nutrition'
import { FoodSearch } from './FoodSearch'

interface MealEditSheetProps {
  /** ID приёма пищи для редактирования (null — лист закрыт) */
  mealId: number | null
  onClose: () => void
}

/** Внутренний тип позиции с ключом для React */
interface EditableItem extends MealItemCreate {
  _key: number
}

export function MealEditSheet({ mealId, onClose }: MealEditSheetProps) {
  // Список редактируемых позиций
  const [items, setItems] = useState<EditableItem[]>([])
  // Флаг загрузки данных
  const [loading, setLoading] = useState(false)
  const updateMeal = useUpdateMeal()

  // Загружаем данные meal при открытии
  useEffect(() => {
    if (!mealId) return
    setLoading(true)
    fetchMeal(mealId)
      .then((meal) => {
        // Конвертируем MealItem[] → EditableItem[] (КБЖУ уже на порцию)
        setItems(
          meal.items.map((item, idx) => ({
            _key: Date.now() + idx,
            name: item.name,
            amount_g: item.amount_g,
            calories: item.calories,
            protein_g: item.protein_g,
            fat_g: item.fat_g,
            carbs_g: item.carbs_g,
          }))
        )
      })
      .catch(() => {
        setItems([])
      })
      .finally(() => setLoading(false))
  }, [mealId])

  // Добавление нового продукта — КБЖУ пересчитывается на размер порции
  const handleFoodSelect = (food: FoodItem) => {
    const serving = food.serving_size_g ?? 100 // порция по умолчанию
    const ratio = serving / 100 // коэффициент пересчёта КБЖУ
    setItems((prev) => [
      ...prev,
      {
        _key: Date.now(),
        name: food.name,
        amount_g: serving,
        calories: Math.round((food.calories ?? 0) * ratio * 10) / 10,
        protein_g: Math.round((food.protein_g ?? 0) * ratio * 10) / 10,
        fat_g: Math.round((food.fat_g ?? 0) * ratio * 10) / 10,
        carbs_g: Math.round((food.carbs_g ?? 0) * ratio * 10) / 10,
      },
    ])
  }

  // Изменение граммовки с пропорциональным пересчётом КБЖУ
  const updateGrams = (index: number, newGrams: number) => {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== index) return item
        const oldGrams = item.amount_g || 100
        const ratio = newGrams / oldGrams
        return {
          ...item,
          amount_g: newGrams,
          calories: Math.round(item.calories * ratio * 10) / 10,
          protein_g: Math.round(item.protein_g * ratio * 10) / 10,
          fat_g: Math.round(item.fat_g * ratio * 10) / 10,
          carbs_g: Math.round(item.carbs_g * ratio * 10) / 10,
        }
      })
    )
  }

  // Удаление позиции
  const removeItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  // Итого калорий
  const totalCal = items.reduce((s, i) => s + i.calories, 0)

  // Сохранение изменений через PUT /api/nutrition/meal/{id}
  const handleSave = () => {
    if (!mealId || items.length === 0) return
    updateMeal.mutate(
      { id: mealId, items: items.map(({ _key, ...rest }) => rest) },
      {
        onSuccess: () => {
          onClose()
        },
      }
    )
  }

  const isOpen = mealId !== null

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Затемнение */}
          <motion.div
            className="fixed inset-0"
            style={{ background: 'rgba(0,0,0,0.5)', zIndex: 50 }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          {/* Лист */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 rounded-t-[24px] p-4 pb-8 max-h-[85vh] overflow-y-auto"
            style={{ background: 'var(--app-bg)', zIndex: 51, borderTop: '1px solid rgba(255,255,255,0.08)' }}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {/* Заголовок */}
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>Редактировать приём</h2>
              <button onClick={onClose}><X size={20} style={{ color: 'var(--app-hint)' }} /></button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 size={24} className="animate-spin" style={{ color: 'var(--app-hint)' }} />
              </div>
            ) : (
              <>
                {/* Поиск для добавления нового продукта */}
                <FoodSearch onSelect={handleFoodSelect} />

                {/* Список позиций */}
                <div className="flex flex-col gap-2 mt-4">
                  {items.map((item, idx) => (
                    <div
                      key={item._key}
                      className="flex items-center gap-2 p-2 rounded-xl border border-white/[0.06]"
                      style={{ background: 'rgba(255,255,255,0.02)' }}
                    >
                      {/* Название и калории */}
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate" style={{ color: 'var(--app-text)' }}>
                          {item.name}
                        </p>
                        <p className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                          {Math.round(item.calories)} ккал · Б{Math.round(item.protein_g)} Ж{Math.round(item.fat_g)} У{Math.round(item.carbs_g)}
                        </p>
                      </div>
                      {/* Граммовка с кнопками ± */}
                      <div className="flex items-center gap-1">
                        <button onClick={() => updateGrams(idx, Math.max(10, item.amount_g - 10))}
                                className="w-6 h-6 rounded-full flex items-center justify-center"
                                style={{ background: 'rgba(255,255,255,0.06)' }}>
                          <Minus size={10} style={{ color: 'var(--app-hint)' }} />
                        </button>
                        <input
                          type="number"
                          value={item.amount_g}
                          onChange={(e) => updateGrams(idx, Math.max(1, Number(e.target.value) || 0))}
                          className="w-12 text-center text-xs bg-transparent outline-none"
                          style={{ color: 'var(--app-text)' }}
                        />
                        <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>г</span>
                        <button onClick={() => updateGrams(idx, item.amount_g + 10)}
                                className="w-6 h-6 rounded-full flex items-center justify-center"
                                style={{ background: 'rgba(255,255,255,0.06)' }}>
                          <Plus size={10} style={{ color: 'var(--app-hint)' }} />
                        </button>
                      </div>
                      {/* Удалить позицию */}
                      <button onClick={() => removeItem(idx)} className="ml-1">
                        <X size={14} style={{ color: '#ef4444' }} />
                      </button>
                    </div>
                  ))}
                </div>

                {/* Итого + кнопка сохранения */}
                {items.length > 0 && (
                  <div className="mt-4 flex items-center justify-between">
                    <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                      Итого: {Math.round(totalCal)} ккал
                    </span>
                    <motion.button
                      onClick={handleSave}
                      disabled={updateMeal.isPending}
                      className="px-6 py-2 rounded-xl text-sm font-medium text-white"
                      style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
                      whileTap={{ scale: 0.95 }}
                    >
                      {updateMeal.isPending ? 'Сохранение...' : 'Сохранить'}
                    </motion.button>
                  </div>
                )}

                {/* Пустой список */}
                {items.length === 0 && !loading && (
                  <p className="text-xs text-center py-6" style={{ color: 'var(--app-hint)' }}>
                    Все продукты удалены. Добавьте через поиск выше.
                  </p>
                )}
              </>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
