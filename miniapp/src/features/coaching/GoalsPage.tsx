/**
 * GoalsPage — список целей с фильтрами (All/Active/Frozen/Achieved) и FAB для создания новой цели.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, ArrowLeft, Search, Loader2 } from 'lucide-react'
import { useGoals, useCreateGoal } from '../../api/coaching'
import type { CreateGoalDto } from '../../api/coaching'
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
    const dto: CreateGoalDto = { title: newTitle.trim(), why_statement: newWhy.trim() || undefined }
    createGoal.mutate(dto, {
      onSuccess: () => { setShowCreate(false); setNewTitle(''); setNewWhy('') },
    })
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-3 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/coaching')}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-xl font-black flex-1" style={{ color: 'var(--app-text)' }}>Мои цели</h1>
      </div>

      {/* Поиск */}
      <div className="px-4 pb-3 shrink-0">
        <div
          className="flex items-center gap-2 rounded-xl px-3 py-2 border border-white/[0.08]"
          style={{ background: 'rgba(255,255,255,0.05)' }}
        >
          <Search size={16} style={{ color: 'var(--app-hint)' }} className="shrink-0" />
          <input
            type="text"
            placeholder="Поиск цели..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="flex-1 text-sm outline-none bg-transparent placeholder-white/30"
            style={{ color: 'var(--app-text)' }}
          />
        </div>
      </div>

      {/* Фильтры */}
      <div className="px-4 pb-4 flex gap-2 overflow-x-auto scrollbar-none shrink-0">
        {FILTERS.map(f => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className="shrink-0 px-4 py-1.5 rounded-full text-sm font-medium transition-all border"
            style={
              filter === f.key
                ? { background: 'rgba(99,102,241,0.25)', color: '#818cf8', borderColor: 'rgba(99,102,241,0.4)' }
                : { background: 'rgba(255,255,255,0.05)', color: 'var(--app-hint)', borderColor: 'rgba(255,255,255,0.08)' }
            }
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Список целей */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin" size={28} style={{ color: '#818cf8' }} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-4xl mb-3">🎯</p>
            <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
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
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-xl flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
      >
        <Plus size={26} style={{ color: '#fff' }} />
      </motion.button>

      {/* Шторка создания цели */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-50 flex items-end"
            onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}
          >
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              className="w-full rounded-t-3xl p-6 pb-10 space-y-4 border-t border-white/[0.08]"
              style={{ background: 'var(--app-bg)' }}
            >
              <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>Новая цель</h2>
              <input
                autoFocus
                type="text"
                placeholder="Название цели..."
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                className="w-full rounded-xl px-4 py-3 text-sm outline-none placeholder-white/30"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  color: 'var(--app-text)',
                  border: '1px solid rgba(255,255,255,0.1)',
                }}
              />
              <textarea
                placeholder="Зачем мне это нужно? (необязательно)"
                value={newWhy}
                onChange={e => setNewWhy(e.target.value)}
                rows={3}
                className="w-full rounded-xl px-4 py-3 text-sm outline-none resize-none placeholder-white/30"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  color: 'var(--app-text)',
                  border: '1px solid rgba(255,255,255,0.1)',
                }}
              />
              <button
                onClick={handleCreate}
                disabled={!newTitle.trim() || createGoal.isPending}
                className="w-full rounded-2xl py-3 font-semibold disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
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
