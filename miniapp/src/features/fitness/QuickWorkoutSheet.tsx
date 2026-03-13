/**
 * Bottom sheet для быстрого логирования тренировки.
 * Выбор типа, добавление упражнений с подходами, кардио-адаптация, сохранение.
 */
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Plus, Trash2, Dumbbell } from 'lucide-react'
import { useCreateSession, type Exercise, type SetData } from '../../api/fitness'
import { ExerciseSearch } from './ExerciseSearch'

interface QuickWorkoutSheetProps {
  open: boolean
  onClose: () => void
}

/** Типы тренировок */
const WORKOUT_TYPES = [
  { value: 'strength', label: 'Силовая', icon: '🏋️' },
  { value: 'cardio', label: 'Кардио', icon: '🏃' },
  { value: 'home', label: 'Дом', icon: '🏠' },
  { value: 'stretching', label: 'Растяжка', icon: '🧘' },
]

/** Категории кардио — длительность/дистанция вместо вес/повторы */
const CARDIO_CATEGORIES = new Set(['cardio', 'flexibility'])

/** Проверяет, является ли упражнение кардио/растяжкой */
function isCardioExercise(exercise: Exercise): boolean {
  return CARDIO_CATEGORIES.has(exercise.category || '')
}

/** Локальное упражнение с подходами */
interface LocalExercise {
  exercise: Exercise
  sets: (SetData & { _key: number })[]
}

export function QuickWorkoutSheet({ open, onClose }: QuickWorkoutSheetProps) {
  const [workoutType, setWorkoutType] = useState('strength')
  const [exercises, setExercises] = useState<LocalExercise[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const createSession = useCreateSession()
  let keyCounter = 0

  // Добавить упражнение из поиска
  const handleExerciseSelect = (ex: Exercise) => {
    const cardio = isCardioExercise(ex)
    setExercises((prev) => [
      ...prev,
      {
        exercise: ex,
        sets: [{
          _key: Date.now(),
          reps: cardio ? 0 : 10,
          weight_kg: 0,
          duration_sec: cardio ? 600 : 0,
          set_type: 'working',
        }],
      },
    ])
    setShowSearch(false)
  }

  // Добавить подход к упражнению
  const addSet = (exIndex: number) => {
    setExercises((prev) =>
      prev.map((ex, i) => {
        if (i !== exIndex) return ex
        const lastSet = ex.sets[ex.sets.length - 1]
        const cardio = isCardioExercise(ex.exercise)
        return {
          ...ex,
          sets: [
            ...ex.sets,
            {
              _key: Date.now() + keyCounter++,
              reps: lastSet?.reps || (cardio ? 0 : 10),
              weight_kg: lastSet?.weight_kg || 0,
              duration_sec: lastSet?.duration_sec || (cardio ? 600 : 0),
              set_type: 'working',
            },
          ],
        }
      })
    )
  }

  // Удалить подход
  const removeSet = (exIndex: number, setIndex: number) => {
    setExercises((prev) =>
      prev.map((ex, i) => {
        if (i !== exIndex) return ex
        return { ...ex, sets: ex.sets.filter((_, si) => si !== setIndex) }
      })
    )
  }

  // Удалить упражнение
  const removeExercise = (exIndex: number) => {
    setExercises((prev) => prev.filter((_, i) => i !== exIndex))
  }

  // Обновить подход
  const updateSet = (exIndex: number, setIndex: number, field: string, value: number) => {
    setExercises((prev) =>
      prev.map((ex, i) => {
        if (i !== exIndex) return ex
        return {
          ...ex,
          sets: ex.sets.map((s, si) => (si === setIndex ? { ...s, [field]: value } : s)),
        }
      })
    )
  }

  // Сохранить тренировку
  const handleSave = async () => {
    if (exercises.length === 0) return
    try {
      await createSession.mutateAsync({
        workout_type: workoutType,
        exercises: exercises.map((ex) => ({
          exercise_id: ex.exercise.id,
          sets: ex.sets.map((s) => ({
            reps: s.reps || undefined,
            weight_kg: s.weight_kg || undefined,
            duration_sec: s.duration_sec || undefined,
            distance_m: s.distance_m || undefined,
            set_type: s.set_type || 'working',
          })),
        })),
      })
      // Сброс и закрытие
      setExercises([])
      setWorkoutType('strength')
      onClose()
    } catch (e) {
      console.error('Ошибка сохранения тренировки:', e)
    }
  }

  // Общий объём
  const totalVolume = exercises.reduce(
    (sum, ex) =>
      sum + ex.sets.reduce((s, set) => s + (set.reps || 0) * (set.weight_kg || 0), 0),
    0
  )
  const totalSets = exercises.reduce((sum, ex) => sum + ex.sets.length, 0)

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Оверлей */}
          <motion.div
            className="fixed inset-0 z-50"
            style={{ background: 'rgba(0,0,0,0.6)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          {/* Sheet */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 z-[51] rounded-t-[24px] border-t border-white/[0.08] flex flex-col"
            style={{ background: 'var(--glass-bg)', maxHeight: '92vh' }}
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {/* Хэндл */}
            <div className="flex justify-center pt-3 pb-2">
              <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.2)' }} />
            </div>

            <div className="flex-1 overflow-y-auto px-4 pb-4">
              {/* Режим поиска упражнений */}
              {showSearch ? (
                <div className="h-[60vh]">
                  <ExerciseSearch onSelect={handleExerciseSelect} onClose={() => setShowSearch(false)} />
                </div>
              ) : (
                <>
                  {/* Заголовок */}
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                      Записать тренировку
                    </h2>
                    <button onClick={onClose}>
                      <X size={22} style={{ color: 'var(--app-hint)' }} />
                    </button>
                  </div>

                  {/* Тип тренировки */}
                  <div className="flex gap-2 mb-4">
                    {WORKOUT_TYPES.map((wt) => (
                      <button
                        key={wt.value}
                        onClick={() => setWorkoutType(wt.value)}
                        className="flex-1 flex flex-col items-center gap-1 py-2 rounded-xl text-xs font-medium transition-colors"
                        style={{
                          background: workoutType === wt.value ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                          color: workoutType === wt.value ? '#a5b4fc' : 'var(--app-hint)',
                          border: workoutType === wt.value ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
                        }}
                      >
                        <span className="text-lg">{wt.icon}</span>
                        {wt.label}
                      </button>
                    ))}
                  </div>

                  {/* Список упражнений */}
                  <div className="space-y-3 mb-4">
                    {exercises.map((ex, exIdx) => {
                      // Определяем, кардио ли упражнение
                      const cardio = isCardioExercise(ex.exercise)
                      return (
                        <div
                          key={`${ex.exercise.id}-${exIdx}`}
                          className="rounded-xl p-3 border border-white/[0.06]"
                          style={{ background: 'rgba(255,255,255,0.03)' }}
                        >
                          {/* Название упражнения */}
                          <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <Dumbbell size={16} style={{ color: '#818cf8' }} />
                              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                                {ex.exercise.name}
                              </span>
                              {/* Бейдж кардио */}
                              {cardio && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                                  style={{ background: 'rgba(251,146,60,0.2)', color: '#fb923c' }}>
                                  кардио
                                </span>
                              )}
                            </div>
                            <button onClick={() => removeExercise(exIdx)} className="p-1">
                              <Trash2 size={14} style={{ color: 'var(--app-hint)' }} />
                            </button>
                          </div>

                          {/* Подходы */}
                          <div className="space-y-1.5">
                            {/* Заголовок колонок — адаптируется для кардио */}
                            <div className="grid grid-cols-[28px_1fr_1fr_28px] gap-2 text-[10px] px-1" style={{ color: 'var(--app-hint)' }}>
                              <span>#</span>
                              {cardio ? (
                                <>
                                  <span>Время (мин)</span>
                                  <span>Дистанция (км)</span>
                                </>
                              ) : (
                                <>
                                  <span>Вес (кг)</span>
                                  <span>Повторы</span>
                                </>
                              )}
                              <span />
                            </div>

                            {ex.sets.map((set, setIdx) => (
                              <div key={set._key} className="grid grid-cols-[28px_1fr_1fr_28px] gap-2 items-center">
                                {/* Номер подхода */}
                                <span className="text-xs text-center" style={{ color: 'var(--app-hint)' }}>
                                  {setIdx + 1}
                                </span>
                                {cardio ? (
                                  <>
                                    {/* Время (минуты → секунды) */}
                                    <input
                                      type="number"
                                      value={set.duration_sec ? Math.round(set.duration_sec / 60) : ''}
                                      onChange={(e) => updateSet(exIdx, setIdx, 'duration_sec', (parseFloat(e.target.value) || 0) * 60)}
                                      className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                      style={{ color: 'var(--app-text)' }}
                                      placeholder="0"
                                      inputMode="decimal"
                                    />
                                    {/* Дистанция (км → м) */}
                                    <input
                                      type="number"
                                      value={set.distance_m ? Math.round(set.distance_m / 100) / 10 : ''}
                                      onChange={(e) => updateSet(exIdx, setIdx, 'distance_m', (parseFloat(e.target.value) || 0) * 1000)}
                                      className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                      style={{ color: 'var(--app-text)' }}
                                      placeholder="0"
                                      inputMode="decimal"
                                    />
                                  </>
                                ) : (
                                  <>
                                    {/* Вес */}
                                    <input
                                      type="number"
                                      value={set.weight_kg || ''}
                                      onChange={(e) => updateSet(exIdx, setIdx, 'weight_kg', parseFloat(e.target.value) || 0)}
                                      className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                      style={{ color: 'var(--app-text)' }}
                                      placeholder="0"
                                      inputMode="decimal"
                                    />
                                    {/* Повторы */}
                                    <input
                                      type="number"
                                      value={set.reps || ''}
                                      onChange={(e) => updateSet(exIdx, setIdx, 'reps', parseInt(e.target.value) || 0)}
                                      className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                      style={{ color: 'var(--app-text)' }}
                                      placeholder="0"
                                      inputMode="numeric"
                                    />
                                  </>
                                )}
                                {/* Удалить подход */}
                                <button onClick={() => removeSet(exIdx, setIdx)} className="p-0.5">
                                  <X size={14} style={{ color: 'var(--app-hint)' }} />
                                </button>
                              </div>
                            ))}
                          </div>

                          {/* Кнопка добавить подход */}
                          <button
                            onClick={() => addSet(exIdx)}
                            className="flex items-center gap-1 mt-2 text-xs font-medium px-2 py-1 rounded-lg"
                            style={{ color: '#818cf8' }}
                          >
                            <Plus size={14} /> Подход
                          </button>
                        </div>
                      )
                    })}
                  </div>

                  {/* Кнопка добавить упражнение */}
                  <button
                    onClick={() => setShowSearch(true)}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-dashed border-white/[0.15] text-sm font-medium mb-4"
                    style={{ color: '#818cf8' }}
                  >
                    <Plus size={18} /> Добавить упражнение
                  </button>

                  {/* Итого + сохранить */}
                  {exercises.length > 0 && (
                    <div className="space-y-3">
                      {/* Сводка */}
                      <div className="flex justify-around text-center text-xs" style={{ color: 'var(--app-hint)' }}>
                        <div>
                          <div className="text-base font-bold" style={{ color: 'var(--app-text)' }}>{exercises.length}</div>
                          упражнений
                        </div>
                        <div>
                          <div className="text-base font-bold" style={{ color: 'var(--app-text)' }}>{totalSets}</div>
                          подходов
                        </div>
                        {totalVolume > 0 && (
                          <div>
                            <div className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
                              {Math.round(totalVolume)}
                            </div>
                            кг объём
                          </div>
                        )}
                      </div>

                      {/* Кнопка сохранить */}
                      <button
                        onClick={handleSave}
                        disabled={createSession.isPending}
                        className="w-full py-3 rounded-xl text-sm font-bold text-white"
                        style={{
                          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                          opacity: createSession.isPending ? 0.6 : 1,
                        }}
                      >
                        {createSession.isPending ? 'Сохранение...' : 'Сохранить тренировку'}
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
