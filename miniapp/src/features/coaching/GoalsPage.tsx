/**
 * GoalsPage — список целей с фильтрами и полноценной формой создания.
 *
 * Исправления:
 *  - FAB получил zIndex: 55 (выше BottomNav z-index:50) и сдвинут вверх от нижней панели
 *  - Форма создания расширена по §14.1: title + area + target_date + why_statement + first_step
 *  - Пустое состояние содержит явную кнопку создания (дублирует FAB)
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, ArrowLeft, Search, Loader2, X } from 'lucide-react'
import { useGoals, useCreateGoal } from '../../api/coaching'
import type { CreateGoalDto } from '../../api/coaching'
import { GoalCard } from './components/GoalCard'

type Filter = 'all' | 'active' | 'frozen' | 'achieved'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'all',      label: 'Все' },
  { key: 'active',   label: 'Активные' },
  { key: 'frozen',   label: 'Заморожены' },
  { key: 'achieved', label: 'Достигнуты' },
]

// Области жизни для выбора при создании цели (§4.1, §14.1)
const AREAS: { key: string; label: string; emoji: string }[] = [
  { key: 'health',        label: 'Здоровье',       emoji: '💪' },
  { key: 'productivity',  label: 'Продуктивность',  emoji: '⚡' },
  { key: 'career',        label: 'Карьера',         emoji: '🚀' },
  { key: 'finance',       label: 'Финансы',         emoji: '💰' },
  { key: 'relationships', label: 'Отношения',       emoji: '❤️' },
  { key: 'mindset',       label: 'Мышление',        emoji: '🧠' },
  { key: 'sport',         label: 'Спорт',           emoji: '🏃' },
  { key: 'personal',      label: 'Личное',          emoji: '🌱' },
]

// Начальное состояние формы создания
const EMPTY_FORM = {
  title:     '',
  why:       '',
  area:      '',
  firstStep: '',
  deadline:  '',
}

export function GoalsPage() {
  const navigate = useNavigate()
  const [filter, setFilter]           = useState<Filter>('active')
  const [search, setSearch]           = useState('')
  const [showCreate, setShowCreate]   = useState(false)
  const [form, setForm]               = useState(EMPTY_FORM)
  const [createError, setCreateError] = useState<string | null>(null)

  // Получаем цели с фильтром по статусу
  const statusParam = filter === 'all' ? undefined : filter
  const { data: goals = [], isLoading } = useGoals(statusParam)
  const createGoal = useCreateGoal()

  // Клиентский поиск по названию
  const filtered = search.trim()
    ? goals.filter(g => g.title.toLowerCase().includes(search.toLowerCase()))
    : goals

  // Сброс и закрытие формы
  const closeCreate = () => {
    setShowCreate(false)
    setForm(EMPTY_FORM)
    setCreateError(null)
  }

  const handleCreate = () => {
    setCreateError(null)
    if (!form.title.trim()) return

    // Собираем DTO только с заполненными полями (§14.1)
    const dto: CreateGoalDto = { title: form.title.trim() }
    if (form.why.trim())       dto.why_statement = form.why.trim()
    if (form.area)             dto.area = form.area
    if (form.firstStep.trim()) dto.first_step = form.firstStep.trim()
    if (form.deadline)         dto.target_date = form.deadline

    createGoal.mutate(dto, {
      onSuccess: () => closeCreate(),
      onError:   () => setCreateError('Не удалось создать цель. Попробуй ещё раз.'),
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
        <h1 className="text-xl font-black flex-1" style={{ color: 'var(--app-text)' }}>
          Мои цели
        </h1>
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
      <div className="flex-1 overflow-y-auto px-4 pb-28 space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin" size={28} style={{ color: '#818cf8' }} />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-4xl mb-3">🎯</p>
            <p className="text-sm mb-5" style={{ color: 'var(--app-hint)' }}>
              {search ? 'Ничего не найдено' : 'Нет целей в этой категории'}
            </p>
            {/* Явный CTA при пустом состоянии — дублирует FAB, чтобы точно не пропустить */}
            {!search && (
              <button
                onClick={() => setShowCreate(true)}
                className="px-6 py-3 rounded-2xl font-semibold text-sm"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
              >
                + Поставить первую цель
              </button>
            )}
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

      {/* FAB — создать цель.
          zIndex: 55 — выше BottomNav (z-index: 50).
          bottom: учитывает высоту BottomNav (~60px) + зазор 1rem. */}
      <motion.button
        whileTap={{ scale: 0.92 }}
        onClick={() => setShowCreate(true)}
        className="fixed right-5 w-14 h-14 rounded-full shadow-xl flex items-center justify-center"
        style={{
          background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
          bottom: 'calc(60px + 1rem)',
          zIndex: 55,
        }}
      >
        <Plus size={26} style={{ color: '#fff' }} />
      </motion.button>

      {/* ── Шторка создания цели (расширенная форма по §14.1) ── */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 flex items-end"
            style={{ zIndex: 60 }}
            onClick={e => e.target === e.currentTarget && closeCreate()}
          >
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 280 }}
              className="w-full rounded-t-3xl border-t border-white/[0.08]"
              style={{ background: 'var(--app-bg)', maxHeight: '90vh', overflowY: 'auto' }}
            >
              {/* Заголовок шторки — sticky чтобы при скролле оставался виден */}
              <div
                className="flex items-center justify-between px-5 pt-5 pb-3 sticky top-0"
                style={{ background: 'var(--app-bg)', zIndex: 1 }}
              >
                <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                  🎯 Новая цель
                </h2>
                <button
                  onClick={closeCreate}
                  className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{ background: 'rgba(255,255,255,0.08)' }}
                >
                  <X size={16} style={{ color: 'var(--app-hint)' }} />
                </button>
              </div>

              <div className="px-5 pb-8 space-y-4">

                {/* 1. Название — обязательное поле */}
                <div>
                  <label
                    className="text-xs font-semibold mb-1.5 block"
                    style={{ color: 'var(--app-hint)' }}
                  >
                    НАЗВАНИЕ *
                  </label>
                  <input
                    autoFocus
                    type="text"
                    placeholder="Например: Выйти на доход 200к в месяц"
                    value={form.title}
                    onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none placeholder-white/30"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      color: 'var(--app-text)',
                      border: '1px solid rgba(255,255,255,0.1)',
                    }}
                  />
                </div>

                {/* 2. Область жизни — сетка 4 колонки */}
                <div>
                  <label
                    className="text-xs font-semibold mb-2 block"
                    style={{ color: 'var(--app-hint)' }}
                  >
                    ОБЛАСТЬ
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {AREAS.map(a => (
                      <button
                        key={a.key}
                        onClick={() => setForm(f => ({ ...f, area: f.area === a.key ? '' : a.key }))}
                        className="flex flex-col items-center gap-1 py-2 px-1 rounded-xl text-xs font-medium transition-all"
                        style={
                          form.area === a.key
                            ? {
                                background: 'rgba(99,102,241,0.25)',
                                color: '#a5b4fc',
                                border: '1px solid rgba(99,102,241,0.4)',
                              }
                            : {
                                background: 'rgba(255,255,255,0.05)',
                                color: 'var(--app-hint)',
                                border: '1px solid rgba(255,255,255,0.07)',
                              }
                        }
                      >
                        <span className="text-base">{a.emoji}</span>
                        <span
                          className="leading-tight text-center"
                          style={{ fontSize: 10 }}
                        >
                          {a.label}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Зачем — why_statement, мотивация */}
                <div>
                  <label
                    className="text-xs font-semibold mb-1.5 block"
                    style={{ color: 'var(--app-hint)' }}
                  >
                    ЗАЧЕМ МНЕ ЭТО?
                  </label>
                  <textarea
                    placeholder="Чем важна эта цель? Что изменится в жизни..."
                    value={form.why}
                    onChange={e => setForm(f => ({ ...f, why: e.target.value }))}
                    rows={2}
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none resize-none placeholder-white/30"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      color: 'var(--app-text)',
                      border: '1px solid rgba(255,255,255,0.1)',
                    }}
                  />
                </div>

                {/* 4. Первый шаг — first_step */}
                <div>
                  <label
                    className="text-xs font-semibold mb-1.5 block"
                    style={{ color: 'var(--app-hint)' }}
                  >
                    ПЕРВЫЙ ШАГ
                  </label>
                  <input
                    type="text"
                    placeholder="Конкретное действие, которое можно сделать уже сегодня"
                    value={form.firstStep}
                    onChange={e => setForm(f => ({ ...f, firstStep: e.target.value }))}
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none placeholder-white/30"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      color: 'var(--app-text)',
                      border: '1px solid rgba(255,255,255,0.1)',
                    }}
                  />
                </div>

                {/* 5. Дедлайн — target_date */}
                <div>
                  <label
                    className="text-xs font-semibold mb-1.5 block"
                    style={{ color: 'var(--app-hint)' }}
                  >
                    ДЕДЛАЙН
                  </label>
                  <input
                    type="date"
                    value={form.deadline}
                    onChange={e => setForm(f => ({ ...f, deadline: e.target.value }))}
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      color: form.deadline ? 'var(--app-text)' : 'var(--app-hint)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      colorScheme: 'dark',
                    }}
                  />
                </div>

                {/* Ошибка создания */}
                {createError && (
                  <p className="text-xs text-center" style={{ color: '#f87171' }}>
                    {createError}
                  </p>
                )}

                {/* Кнопка отправки */}
                <button
                  onClick={handleCreate}
                  disabled={!form.title.trim() || createGoal.isPending}
                  className="w-full rounded-2xl py-4 font-bold disabled:opacity-40"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
                >
                  {createGoal.isPending ? 'Создаём...' : '🎯 Создать цель'}
                </button>

              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
