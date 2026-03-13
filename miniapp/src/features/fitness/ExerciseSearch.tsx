/**
 * Поиск упражнений с фильтрами по категории и группе мышц.
 * Используется в QuickWorkoutSheet для добавления упражнений.
 */
import { useState } from 'react'
import { Search, Dumbbell, X } from 'lucide-react'
import { useExerciseSearch, type Exercise } from '../../api/fitness'

// Категории для фильтра
const CATEGORIES = [
  { value: '', label: 'Все' },
  { value: 'strength', label: 'Силовые' },
  { value: 'cardio', label: 'Кардио' },
  { value: 'home', label: 'Дом' },
  { value: 'flexibility', label: 'Растяжка' },
]

// Группы мышц для фильтра
const MUSCLE_GROUPS = [
  { value: '', label: 'Все' },
  { value: 'chest', label: 'Грудь' },
  { value: 'back', label: 'Спина' },
  { value: 'legs', label: 'Ноги' },
  { value: 'shoulders', label: 'Плечи' },
  { value: 'biceps', label: 'Бицепс' },
  { value: 'triceps', label: 'Трицепс' },
  { value: 'core', label: 'Кор' },
  { value: 'full_body', label: 'Всё тело' },
]

interface ExerciseSearchProps {
  onSelect: (exercise: Exercise) => void
  onClose?: () => void
}

export function ExerciseSearch({ onSelect, onClose }: ExerciseSearchProps) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [muscleGroup, setMuscleGroup] = useState('')

  // Запрос к API с debounce через React Query
  const { data: exercises, isLoading } = useExerciseSearch(query, category || undefined, muscleGroup || undefined)

  return (
    <div className="flex flex-col h-full">
      {/* Заголовок с кнопкой закрытия */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
          Выбери упражнение
        </h3>
        {onClose && (
          <button onClick={onClose} className="p-1 rounded-full" style={{ color: 'var(--app-hint)' }}>
            <X size={20} />
          </button>
        )}
      </div>

      {/* Поле поиска */}
      <div
        className="flex items-center gap-2 px-3 py-2.5 rounded-xl mb-3 border border-white/[0.08]"
        style={{ background: 'rgba(255,255,255,0.04)' }}
      >
        <Search size={18} style={{ color: 'var(--app-hint)' }} />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Жим, присед, бег..."
          className="flex-1 bg-transparent text-sm outline-none"
          style={{ color: 'var(--app-text)' }}
          autoFocus
        />
        {query && (
          <button onClick={() => setQuery('')} className="p-0.5">
            <X size={16} style={{ color: 'var(--app-hint)' }} />
          </button>
        )}
      </div>

      {/* Фильтр по категории — горизонтальный скролл */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-2 no-scrollbar">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => setCategory(cat.value)}
            className="px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors"
            style={{
              background: category === cat.value ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
              color: category === cat.value ? '#a5b4fc' : 'var(--app-hint)',
              border: category === cat.value ? '1px solid rgba(99,102,241,0.4)' : '1px solid transparent',
            }}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Фильтр по группе мышц */}
      <div className="flex gap-1.5 overflow-x-auto pb-2 mb-3 no-scrollbar">
        {MUSCLE_GROUPS.map((mg) => (
          <button
            key={mg.value}
            onClick={() => setMuscleGroup(mg.value)}
            className="px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors"
            style={{
              background: muscleGroup === mg.value ? 'rgba(139,92,246,0.3)' : 'rgba(255,255,255,0.06)',
              color: muscleGroup === mg.value ? '#c4b5fd' : 'var(--app-hint)',
              border: muscleGroup === mg.value ? '1px solid rgba(139,92,246,0.4)' : '1px solid transparent',
            }}
          >
            {mg.label}
          </button>
        ))}
      </div>

      {/* Результаты */}
      <div className="flex-1 overflow-y-auto space-y-1.5">
        {isLoading && (
          <div className="text-center py-6 text-sm" style={{ color: 'var(--app-hint)' }}>
            Поиск...
          </div>
        )}

        {/* Сообщение при пустых результатах */}
        {!isLoading && (query.length >= 2 || !!category || !!muscleGroup) && exercises?.length === 0 && (
          <div className="text-center py-6 text-sm" style={{ color: 'var(--app-hint)' }}>
            Ничего не найдено
          </div>
        )}

        {/* Подсказка если нет ни текста ни фильтров */}
        {!isLoading && query.length < 2 && !category && !muscleGroup && (
          <div className="text-center py-6 text-sm" style={{ color: 'var(--app-hint)' }}>
            Введи название или выбери категорию
          </div>
        )}

        {exercises?.map((ex) => (
          <button
            key={ex.id}
            onClick={() => onSelect(ex)}
            className="w-full text-left flex items-center gap-3 p-3 rounded-xl transition-colors"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            {/* Иконка группы мышц */}
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'rgba(99,102,241,0.15)' }}
            >
              <Dumbbell size={18} style={{ color: '#818cf8' }} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate" style={{ color: 'var(--app-text)' }}>
                {ex.name}
              </div>
              <div className="text-xs flex gap-2 mt-0.5" style={{ color: 'var(--app-hint)' }}>
                <span>{_muscleGroupRu(ex.muscle_group)}</span>
                <span>·</span>
                <span>{ex.equipment || 'Без оборудования'}</span>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

/** Перевод группы мышц */
function _muscleGroupRu(mg: string | null): string {
  const map: Record<string, string> = {
    chest: 'Грудь', back: 'Спина', legs: 'Ноги', shoulders: 'Плечи',
    biceps: 'Бицепс', triceps: 'Трицепс', core: 'Кор', full_body: 'Всё тело',
  }
  return mg ? map[mg] || mg : ''
}
