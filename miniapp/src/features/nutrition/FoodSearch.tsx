/**
 * Поиск продуктов с debounce, секцией избранных и toggle ⭐.
 */
import { useState, useEffect } from 'react'
import { Search, Star } from 'lucide-react'
import { useFoodSearch, useFavorites, useToggleFavorite, type FoodItem } from '../../api/nutrition'

interface FoodSearchProps {
  onSelect: (food: FoodItem) => void
}

export function FoodSearch({ onSelect }: FoodSearchProps) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')

  // Debounce 300мс
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query), 300)
    return () => clearTimeout(t)
  }, [query])

  const { data: results, isLoading } = useFoodSearch(debouncedQuery)
  const { data: favorites } = useFavorites()
  const toggleFav = useToggleFavorite()

  const handleSelect = (food: FoodItem) => {
    onSelect(food)
    setQuery('')
    setDebouncedQuery('')
  }

  // Обработчик toggle избранного (stopPropagation чтобы не выбирать продукт)
  const handleToggleFav = (e: React.MouseEvent, foodId: number) => {
    e.stopPropagation()
    toggleFav.mutate(foodId)
  }

  // Рендер одной строки продукта
  const renderFoodRow = (food: FoodItem) => (
    <button
      key={food.id}
      onClick={() => handleSelect(food)}
      className="w-full px-3 py-2 text-left hover:bg-white/[0.04] flex justify-between items-center gap-2"
    >
      {/* Кнопка ⭐ */}
      <button
        onClick={(e) => handleToggleFav(e, food.id)}
        className="shrink-0 p-0.5"
      >
        <Star
          size={14}
          fill={food.is_favorite ? '#f59e0b' : 'none'}
          stroke={food.is_favorite ? '#f59e0b' : 'rgba(255,255,255,0.2)'}
        />
      </button>
      <span className="flex-1 text-sm truncate" style={{ color: 'var(--app-text)' }}>{food.name}</span>
      <span className="text-[10px] shrink-0" style={{ color: 'var(--app-hint)' }}>
        {food.calories} ккал
      </span>
    </button>
  )

  // Показываем избранные когда поле пустое
  const showFavorites = !debouncedQuery && favorites && favorites.length > 0

  return (
    <div className="relative">
      {/* Поле ввода */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-xl border border-white/[0.08]"
           style={{ background: 'rgba(255,255,255,0.04)' }}>
        <Search size={14} style={{ color: 'var(--app-hint)' }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Поиск продукта..."
          className="flex-1 bg-transparent text-sm outline-none"
          style={{ color: 'var(--app-text)' }}
        />
      </div>

      {/* Секция «⭐ Избранные» при пустом запросе */}
      {showFavorites && (
        <div className="mt-2 rounded-xl border border-white/[0.08] overflow-hidden max-h-40 overflow-y-auto"
             style={{ background: 'var(--glass-bg)', backdropFilter: 'blur(20px)' }}>
          <p className="px-3 py-1.5 text-[10px] font-medium" style={{ color: 'var(--app-hint)' }}>
            ⭐ Избранные
          </p>
          {favorites!.map(renderFoodRow)}
        </div>
      )}

      {/* Результаты поиска */}
      {debouncedQuery.length >= 2 && (
        <div className="absolute left-0 right-0 mt-1 rounded-xl border border-white/[0.08] overflow-hidden max-h-48 overflow-y-auto"
             style={{ background: 'var(--glass-bg)', backdropFilter: 'blur(20px)', zIndex: 20 }}>
          {isLoading && (
            <p className="px-3 py-2 text-xs" style={{ color: 'var(--app-hint)' }}>Поиск...</p>
          )}
          {results && results.length === 0 && (
            <p className="px-3 py-2 text-xs" style={{ color: 'var(--app-hint)' }}>Ничего не найдено</p>
          )}
          {results?.map(renderFoodRow)}
        </div>
      )}
    </div>
  )
}
