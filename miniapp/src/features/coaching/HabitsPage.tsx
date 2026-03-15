/**
 * HabitsPage — экран привычек.
 * Два режима: «Сегодня» (1-tap лог ✅/❌) и «Все» (статистика + процент выполнения).
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Plus, Loader2 } from 'lucide-react'
import { useHabits, useLogHabit, useMissHabit, useCreateHabit, useHabitTemplates } from '../../api/coaching'
import type { CreateHabitDto } from '../../api/coaching'
import { usePrompts } from '../../api/coaching'
import { CoachPromptBubble } from './components/CoachPromptBubble'
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
  const { data: prompts = [] } = usePrompts('habits')
  const logHabit = useLogHabit()
  const missHabit = useMissHabit()
  const createHabit = useCreateHabit()

  const handleCreate = () => {
    if (!newTitle.trim()) return
    const dto: CreateHabitDto = { title: newTitle.trim(), emoji: newEmoji }
    createHabit.mutate(dto, {
      onSuccess: () => { setShowCreate(false); setNewTitle(''); setNewEmoji('🎯') },
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
        <h1 className="text-xl font-black flex-1" style={{ color: 'var(--app-text)' }}>Привычки</h1>
      </div>

      {/* Переключатель режима */}
      <div className="px-4 pb-4 shrink-0">
        <div
          className="flex rounded-xl p-1 gap-1"
          style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.06)' }}
        >
          {(['today', 'all'] as Mode[]).map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="flex-1 py-2 rounded-lg text-sm font-semibold transition-all"
              style={
                mode === m
                  ? { background: 'rgba(99,102,241,0.25)', color: '#818cf8' }
                  : { background: 'transparent', color: 'var(--app-hint)' }
              }
            >
              {m === 'today' ? 'Сегодня' : 'Все привычки'}
            </button>
          ))}
        </div>
      </div>

      {/* Список привычек */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-2">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin" size={28} style={{ color: '#a78bfa' }} />
          </div>
        ) : habits.length === 0 ? (
          <div className="py-8 space-y-4">
            <div className="text-center">
              <p className="text-4xl mb-3">🌱</p>
              <p className="text-sm" style={{ color: 'var(--app-hint)' }}>Нет активных привычек</p>
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
              className="w-full text-center text-sm font-semibold py-2"
              style={{ color: '#818cf8' }}
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
                  onDone={mode === 'today' ? () => logHabit.mutate(h.id) : undefined}
                  onMiss={mode === 'today' ? () => missHabit.mutate(h.id) : undefined}
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
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-xl flex items-center justify-center"
        style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)' }}
      >
        <Plus size={26} style={{ color: '#fff' }} />
      </motion.button>

      {/* Шторка создания привычки */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-50 flex items-end"
            onClick={(e) => e.target === e.currentTarget && setShowCreate(false)}
          >
            <motion.div
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              className="w-full rounded-t-3xl p-6 pb-10 space-y-4 border-t border-white/[0.08]"
              style={{ background: 'var(--app-bg)' }}
            >
              <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>Новая привычка</h2>

              {/* Шаблоны */}
              {templates.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wide mb-2" style={{ color: 'var(--app-hint)' }}>Быстрый выбор</p>
                  <div className="flex flex-wrap gap-2">
                    {templates.slice(0, 8).map((t: any) => (
                      <button
                        key={t.id}
                        onClick={() => { setNewTitle(t.title); setNewEmoji(t.emoji ?? '🎯') }}
                        className="px-3 py-1.5 rounded-xl text-sm flex items-center gap-1.5 border border-white/[0.08]"
                        style={{ background: 'rgba(255,255,255,0.05)', color: 'var(--app-text)' }}
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
                  placeholder="🎯"
                  value={newEmoji}
                  onChange={e => setNewEmoji(e.target.value)}
                  maxLength={2}
                  className="w-14 rounded-xl px-3 py-3 text-center text-lg outline-none"
                  style={{
                    background: 'rgba(255,255,255,0.06)',
                    color: 'var(--app-text)',
                    border: '1px solid rgba(255,255,255,0.1)',
                  }}
                />
                <input
                  autoFocus
                  type="text"
                  placeholder="Название привычки..."
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  className="flex-1 rounded-xl px-4 py-3 text-sm outline-none placeholder-white/30"
                  style={{
                    background: 'rgba(255,255,255,0.06)',
                    color: 'var(--app-text)',
                    border: '1px solid rgba(255,255,255,0.1)',
                  }}
                />
              </div>
              <button
                onClick={handleCreate}
                disabled={!newTitle.trim() || createHabit.isPending}
                className="w-full rounded-2xl py-3 font-semibold disabled:opacity-40"
                style={{ background: 'linear-gradient(135deg, #8b5cf6, #6366f1)', color: '#fff' }}
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
