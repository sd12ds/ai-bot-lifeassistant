/**
 * GoalsPage — список целей с фильтрами (All/Active/Frozen/Achieved) и FAB для создания новой цели.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, ArrowLeft, Search, Loader2 } from 'lucide-react'
import { useGoals, useCreateGoal } from '../../api/coaching'
import type { CreateGoalDTO } from '../../api/coaching'
import { GoalCard } from './components/GoalCard'

type Filter = 'all' | 'active' | 'frozen' | 'achieved'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'active', label: 'Активные' },
  { key: 'frozen', label: 'Заморожены' },
  { key: 'achieved', label: 'Достигнуты' },
]

export function GoalsPage() {
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>('active')
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newWhy, setNewWhy] = useState('')

  // Получаем цели с фильтром по статусу
  const statusParam = filter === 'all' ? undefined : filter
  const { data: goals = [], isLoading } = useGoals(statusParam)
  const createGoal = useCreateGoal()

  // Клиентский поиск по названию
  const filtered = search.trim()
    ? goals.filter(g => g.title.toLowerCase().includes(search.toLowerCase()))
    : goals

  const handleCreate = () => {
    if (!newTitle.trim()) return
    const dto: CreateGoalDTO = { title: newTitle.trim(), why_statement: newWhy.trim() || undefined }
    createGoal.mutate(dto, {
      onSuccess: () => { setShowCreate(false); setNewTitle(''); setNewWhy('') },
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3">
        <button onClick={() => navigate('/coaching')} className="text-gray-500">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-xl font-black text-gray-900 flex-1">Мои цели</h1>
      </div>

      {/* Поиск */}
      <div className="px-4 pb-3">
        <div className="flex items-center gap-2 bg-white rounded-xl px-3 py-2 shadow-sm">
          <Search size={16} className="text-gray-400 shrink-0" />
          <input
            type="text"
            placeholder="Поиск цели..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1 text-sm outline-none bg-transparent text-gray-800 placeholder-gray-400"
          />
        </div>
      </div>

      {/* Фильтры */}
      <div className="px-4 pb-4 flex gap-2 overflow-x-auto scrollbar-none">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
              filter === f.key
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'bg-white text-gray-600 border border-gray-200'
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Список целей */}
      <div className="px-4 space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin text-indigo-400" size={28} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-4xl mb-3">🎯</p>
            <p className="text-gray-500 text-sm">
              {search ? 'Ничего не найдено' : 'Нет целей в этой категории'}
            </p>
          </div>
        ) : (
          <AnimatePresence>
            {filtered.map((g, i) => (
              <motion.div
                key={g.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ delay: i * 0.04 }}
              >
                <GoalCard goal={g} onClick={() => navigate(`/coaching/goals/${g.id}`)} />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* FAB — создать цель */}
      <motion.button
        whileTap={{ scale: 0.92 }}
        onClick={() => setShowCreate(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-indigo-600 text-white rounded-full shadow-xl flex items-center justify-center"
      >
        <Plus size={26} />
      </motion.button>

      {/* Шторка создания цели */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-50 flex items-end"
            onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}
          >
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              className="w-full bg-white rounded-t-3xl p-6 pb-10 space-y-4"
            >
              <h2 className="text-lg font-bold text-gray-900">Новая цель</h2>
              <input
                autoFocus
                type="text"
                placeholder="Название цели..."
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-400"
              />
              <textarea
                placeholder="Зачем мне это нужно? (необязательно)"
                value={newWhy}
                onChange={e => setNewWhy(e.target.value)}
                rows={3}
                className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-400 resize-none"
              />
              <button
                onClick={handleCreate}
                disabled={!newTitle.trim() || createGoal.isPending}
                className="w-full bg-indigo-600 text-white rounded-2xl py-3 font-semibold disabled:opacity-50"
              >
                {createGoal.isPending ? 'Создаём...' : 'Создать'}
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
