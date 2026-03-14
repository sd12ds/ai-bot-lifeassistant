/**
 * HabitsPage — экран привычек.
 * Два режима: "Сегодня" (1-tap лог ✅/❌) и "Все" (статистика + процент выполнения).
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Plus, Loader2 } from 'lucide-react'
import { useHabits, useLogHabit, useMissHabit, useCreateHabit, useHabitTemplates } from '../../api/coaching'
import type { CreateHabitDTO } from '../../api/coaching'
import { HabitCard } from './components/HabitCard'

type Mode = 'today' | 'all'

export function HabitsPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>('today')
  const [showCreate, setShowCreate] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newEmoji, setNewEmoji] = useState('🎯')

  const { data: habits = [], isLoading } = useHabits()
  const { data: templates = [] } = useHabitTemplates()
  const { data: prompts = [] } = usePrompts(empty_habits)
  const logHabit = useLogHabit()
  const missHabit = useMissHabit()
  const createHabit = useCreateHabit()

  const handleCreate = () => {
    if (!newTitle.trim()) return
    const dto: CreateHabitDTO = { title: newTitle.trim(), emoji: newEmoji }
    createHabit.mutate(dto, {
      onSuccess: () => { setShowCreate(false); setNewTitle(''); setNewEmoji('🎯') },
    })
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3">
        <button onClick={() => navigate('/coaching')} className="text-gray-500">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-xl font-black text-gray-900 flex-1">Привычки</h1>
      </div>

      {/* Переключатель режима */}
      <div className="px-4 pb-4">
        <div className="flex bg-gray-200 rounded-xl p-1">
          {(['today', 'all'] as Mode[]).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${
                mode === m ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'
              }`}
            >
              {m === 'today' ? 'Сегодня' : 'Все привычки'}
            </button>
          ))}
        </div>
      </div>

      {/* Список привычек */}
      <div className="px-4 space-y-2">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin text-purple-400" size={28} />
          </div>
        ) : habits.length === 0 ? (
          <div className="py-8 space-y-4">
            <div className="text-center">
              <p className="text-4xl mb-3">🌱</p>
              <p className="text-gray-500 text-sm">Нет активных привычек</p>
            </div>
            {prompts.length > 0 && (
              <CoachPromptBubble
                text={prompts[0]}
                action="Добавить привычку"
                onAction={() => setShowCreate(true)}
              />
            )}
            <button
              onClick={() => setShowCreate(true)}
              className="w-full text-center text-indigo-600 text-sm font-semibold py-2"
            >
              + Добавить первую
            </button>
          </div>
        ) : (
          <AnimatePresence>
            {habits.map((h, i) => (
              <motion.div
                key={h.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <HabitCard
                  habit={h}
                  todayStatus={
                    mode === 'today'
                      ? (h.today_done === true ? true : h.today_done === false ? false : undefined)
                      : undefined
                  }
                  onDone={mode === 'today' ? () => logHabit.mutate({ habitId: h.id, data: { note: '' } }) : undefined}
                  onMiss={mode === 'today' ? () => missHabit.mutate({ habitId: h.id, data: { reason: '' } }) : undefined}
                  showStats={mode === 'all'}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* FAB */}
      <motion.button
        whileTap={{ scale: 0.92 }}
        onClick={() => setShowCreate(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-purple-600 text-white rounded-full shadow-xl flex items-center justify-center"
      >
        <Plus size={26} />
      </motion.button>

      {/* Шторка создания привычки */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-50 flex items-end"
            onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}
          >
            <motion.div
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              className="w-full bg-white rounded-t-3xl p-6 pb-10 space-y-4"
            >
              <h2 className="text-lg font-bold text-gray-900">Новая привычка</h2>

              {/* Шаблоны */}
              {templates.length > 0 && (
                <div>
                  <p className="text-xs text-gray-400 mb-2 uppercase tracking-wide">Быстрый выбор</p>
                  <div className="flex flex-wrap gap-2">
                    {templates.slice(0, 8).map(t => (
                      <button
                        key={t.id}
                        onClick={() => { setNewTitle(t.title); setNewEmoji(t.emoji ?? '🎯') }}
                        className="px-3 py-1.5 bg-gray-100 rounded-xl text-sm flex items-center gap-1.5"
                      >
                        <span>{t.emoji ?? '🎯'}</span> {t.title}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex items-center gap-3">
                <input
                  type="text"
                  placeholder="Эмодзи"
                  value={newEmoji}
                  onChange={e => setNewEmoji(e.target.value)}
                  maxLength={2}
                  className="w-14 border border-gray-200 rounded-xl px-3 py-3 text-center text-lg outline-none"
                />
                <input
                  autoFocus
                  type="text"
                  placeholder="Название привычки..."
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  className="flex-1 border border-gray-200 rounded-xl px-4 py-3 text-sm outline-none focus:border-purple-400"
                />
              </div>
              <button
                onClick={handleCreate}
                disabled={!newTitle.trim() || createHabit.isPending}
                className="w-full bg-purple-600 text-white rounded-2xl py-3 font-semibold disabled:opacity-50"
              >
                {createHabit.isPending ? 'Добавляем...' : 'Добавить'}
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
