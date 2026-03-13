/**
 * Нижний лист создания приёма пищи.
 * Выбор типа, поиск продуктов, граммовка, итого КБЖУ.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Minus, Plus } from 'lucide-react'
import { useCreateMeal, useSuggestions, type MealItemCreate, type FoodItem, type Meal } from '../../api/nutrition'
import { RotateCcw } from 'lucide-react'
import { FoodSearch } from './FoodSearch'

interface MealCreateSheetProps {
  open: boolean
  onClose: () => void
}

/** Типы приёмов пищи */
const MEAL_TYPES = [
  { value: 'breakfast', label: 'Завтрак', icon: '🌅' },
  { value: 'lunch',    label: 'Обед',    icon: '☀️' },
  { value: 'dinner',   label: 'Ужин',    icon: '🌙' },
  { value: 'snack',    label: 'Перекус', icon: '🍎' },
]

export function MealCreateSheet({ open, onClose }: MealCreateSheetProps) {
  const [mealType, setMealType] = useState('lunch')
  const [items, setItems] = useState<(MealItemCreate & { _key: number })[]>([])
  const createMeal = useCreateMeal()
  const { data: suggestions } = useSuggestions(mealType)
  let keyCounter = 0

  // Добавление продукта из поиска
  // Добавление продукта — КБЖУ пересчитывается на размер порции
  const handleFoodSelect = (food: FoodItem) => {
    const serving = food.serving_size_g ?? 100 // порция по умолчанию
    const ratio = serving / 100 // коэффициент пересчёта КБЖУ
    setItems((prev) => [
      ...prev,
      {
        _key: Date.now() + keyCounter++,
        name: food.name,
        amount_g: serving,
        calories: Math.round((food.calories ?? 0) * ratio * 10) / 10,
        protein_g: Math.round((food.protein_g ?? 0) * ratio * 10) / 10,
        fat_g: Math.round((food.fat_g ?? 0) * ratio * 10) / 10,
        carbs_g: Math.round((food.carbs_g ?? 0) * ratio * 10) / 10,
      },
    ])
  }

  // Изменение граммовки — пересчёт КБЖУ пропорционально
  const updateGrams = (index: number, newGrams: number) => {
    setItems((prev) =>
      prev.map((item, i) => {
        if (i !== index) return item
        const ratio = newGrams / (item.amount_g || 100)
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

  // Итого
  const totalCal = items.reduce((s, i) => s + i.calories, 0)

  // Повторить приём пищи — добавить все его позиции
  const handleRepeatMeal = (meal: Meal) => {
    const newItems = meal.items.map((mi) => ({
      _key: Date.now() + keyCounter++,
      name: mi.name,
      amount_g: mi.amount_g,
      calories: mi.calories,
      protein_g: mi.protein_g,
      fat_g: mi.fat_g,
      carbs_g: mi.carbs_g,
    }))
    setItems((prev) => [...prev, ...newItems])
  }

  // Сохранение
  const handleSave = () => {
    if (items.length === 0) return
    createMeal.mutate(
      { meal_type: mealType, items: items.map(({ _key, ...rest }) => rest) },
      {
        onSuccess: () => {
          setItems([])
          onClose()
        },
      }
    )
  }

  return (
    <AnimatePresence>
      {open && (
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
              <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>Новый приём пищи</h2>
              <button onClick={onClose}><X size={20} style={{ color: 'var(--app-hint)' }} /></button>
            </div>

            {/* Тип */}
            <div className="flex gap-2 mb-4">
              {MEAL_TYPES.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setMealType(t.value)}
                  className="flex-1 py-2 rounded-xl text-xs font-medium text-center border"
                  style={{
                    borderColor: mealType === t.value ? '#818cf8' : 'rgba(255,255,255,0.08)',
                    background: mealType === t.value ? 'rgba(99,102,241,0.15)' : 'transparent',
                    color: mealType === t.value ? '#818cf8' : 'var(--app-hint)',
                  }}
                >
                  {t.icon} {t.label}
                </button>
              ))}
            </div>

            {/* Поиск */}
            <FoodSearch onSelect={handleFoodSelect} />

            {/* 🔁 Частые продукты */}
            {suggestions?.frequent_foods && suggestions.frequent_foods.length > 0 && items.length === 0 && (
              <div className="mt-3">
                <p className="text-[10px] font-medium mb-1.5" style={{ color: 'var(--app-hint)' }}>
                  🔁 Частые
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.frequent_foods.map((food) => (
                    <button
                      key={food.id}
                      onClick={() => handleFoodSelect(food)}
                      className="px-2.5 py-1 rounded-lg text-[11px] border border-white/[0.08]"
                      style={{ color: 'var(--app-text)', background: 'rgba(255,255,255,0.04)' }}
                    >
                      {food.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* 🔄 Повторить последний приём */}
            {suggestions?.recent_meals && suggestions.recent_meals.length > 0 && items.length === 0 && (
              <div className="mt-3">
                <p className="text-[10px] font-medium mb-1.5" style={{ color: 'var(--app-hint)' }}>
                  🔄 Повторить
                </p>
                <div className="flex flex-col gap-1.5">
                  {suggestions.recent_meals.map((meal) => (
                    <button
                      key={meal.id}
                      onClick={() => handleRepeatMeal(meal)}
                      className="flex items-center gap-2 px-3 py-2 rounded-xl border border-white/[0.08] text-left"
                      style={{ background: 'rgba(255,255,255,0.02)' }}
                    >
                      <RotateCcw size={12} style={{ color: 'var(--app-hint)' }} />
                      <div className="flex-1 min-w-0">
                        <p className="text-[11px] truncate" style={{ color: 'var(--app-text)' }}>
                          {meal.items.map((i) => i.name).join(', ')}
                        </p>
                        <p className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                          {Math.round(meal.total_calories)} ккал
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Список добавленных */}
            <div className="flex flex-col gap-2 mt-4">
              {items.map((item, idx) => (
                <div
                  key={item._key}
                  className="flex items-center gap-2 p-2 rounded-xl border border-white/[0.06]"
                  style={{ background: 'rgba(255,255,255,0.02)' }}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate" style={{ color: 'var(--app-text)' }}>
                      {item.name}
                    </p>
                    <p className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                      {Math.round(item.calories)} ккал
                    </p>
                  </div>
                  {/* Граммовка */}
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
                  {/* Удалить */}
                  <button onClick={() => removeItem(idx)} className="ml-1">
                    <X size={14} style={{ color: '#ef4444' }} />
                  </button>
                </div>
              ))}
            </div>

            {/* Итого + кнопка */}
            {items.length > 0 && (
              <div className="mt-4 flex items-center justify-between">
                <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  Итого: {Math.round(totalCal)} ккал
                </span>
                <motion.button
                  onClick={handleSave}
                  disabled={createMeal.isPending}
                  className="px-6 py-2 rounded-xl text-sm font-medium text-white"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
                  whileTap={{ scale: 0.95 }}
                >
                  {createMeal.isPending ? 'Сохранение...' : 'Сохранить'}
                </motion.button>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
