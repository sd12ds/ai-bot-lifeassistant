/**
 * GoalDetailPage — полный экран управления целью:
 * мета-блок (область, статус, дедлайн, first_step, frozen_reason),
 * прогресс-бар, воронка этапов с добавлением, привязанные привычки,
 * история чекинов, bottom sheet обновления прогресса, расширенная sticky-панель.
 */
import { useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Snowflake, PlayCircle, Trophy,
  Loader2, Plus, RotateCcw, TrendingUp, X, Calendar, Clock,
  MoreHorizontal,
} from 'lucide-react'
import {
  useGoal, useMilestones, useCompleteMilestone,
  useFreezeGoal, useResumeGoal, useAchieveGoal,
  useCheckInHistory, useUpdateGoal,
  useCreateMilestone, useRestartGoal, useHabitsByGoal,
} from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'
import { CoachPromptBubble } from './components/CoachPromptBubble'

// Словарь emoji для областей жизни
const AREA_EMOJI: Record<string, string> = {
  health: '💪',
  productivity: '⚡',
  career: '🚀',
  finance: '💰',
  relationships: '❤️',
  mindset: '🧠',
  sport: '🏃',
  personal: '🌱',
}

// Человекочитаемые названия областей
const AREA_LABEL: Record<string, string> = {
  health: 'Здоровье',
  productivity: 'Продуктивность',
  career: 'Карьера',
  finance: 'Финансы',
  relationships: 'Отношения',
  mindset: 'Мышление',
  sport: 'Спорт',
  personal: 'Личное',
}

/** Вычислить кол-во дней до дедлайна (отрицательное — просрочен) */
function daysUntil(dateStr: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const target = new Date(dateStr)
  target.setHours(0, 0, 0, 0)
  return Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
}

/** Цвет и метка дедлайна */
function deadlineInfo(dateStr: string | null): { color: string; label: string } | null {
  if (!dateStr) return null
  const days = daysUntil(dateStr)
  const date = new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  if (days > 30)  return { color: '#4ade80', label: `до ${date} · ${days} дн.` }
  if (days >= 7)  return { color: '#fbbf24', label: `до ${date} · ${days} дн.` }
  if (days >= 1)  return { color: '#f87171', label: `до ${date} · ${days} дн.` }
  if (days === 0) return { color: '#f87171', label: 'сегодня дедлайн!' }
  return { color: '#f87171', label: `просрочена на ${Math.abs(days)} дн.` }
}

/** Бейдж статуса цели */
function StatusBadge({ goal }: { goal: { status: string; is_frozen: boolean; target_date?: string | null } }) {
  if (goal.status === 'achieved') {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full font-medium"
        style={{ background: 'rgba(74,222,128,0.15)', color: '#4ade80' }}>
        ✅ Достигнута
      </span>
    )
  }
  if (goal.is_frozen) {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full font-medium"
        style={{ background: 'rgba(148,163,184,0.15)', color: '#94a3b8' }}>
        ❄️ Заморожена
      </span>
    )
  }
  const isOverdue = goal.target_date && daysUntil(goal.target_date) < 0
  if (isOverdue) {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full font-medium"
        style={{ background: 'rgba(248,113,113,0.15)', color: '#f87171' }}>
        🔴 Просрочена
      </span>
    )
  }
  return (
    <span className="text-xs px-2 py-0.5 rounded-full font-medium"
      style={{ background: 'rgba(74,222,128,0.15)', color: '#4ade80' }}>
      🟢 Активна
    </span>
  )
}

export function GoalDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const goalId = Number(id)

  // Состояния UI
  const [showProgressSheet, setShowProgressSheet] = useState(false)
  const [showAddMilestone, setShowAddMilestone]   = useState(false)
  const [showMoreMenu, setShowMoreMenu]           = useState(false)
  const [confirmRestart, setConfirmRestart]       = useState(false)
  const [offerAchieve, setOfferAchieve]           = useState(false)

  // Форма добавления этапа
  const [newMilestoneTitle, setNewMilestoneTitle] = useState('')
  const [newMilestoneDue, setNewMilestoneDue]     = useState('')

  // Bottom sheet прогресса
  const [progressValue, setProgressValue] = useState(0)
  const [progressNote, setProgressNote]   = useState('')

  // Реф для прокрутки к форме этапа
  const milestoneFormRef = useRef<HTMLDivElement>(null)

  // Данные
  const { data: goal, isLoading } = useGoal(goalId)
  const { data: milestones = [] }  = useMilestones(goalId)
  const { data: history = [] }     = useCheckInHistory(5, goalId)
  const { data: habits = [] }      = useHabitsByGoal(goalId)

  // Мутации
  const completeMilestone = useCompleteMilestone()
  const createMilestone   = useCreateMilestone()
  const freezeGoal        = useFreezeGoal()
  const resumeGoal        = useResumeGoal()
  const achieveGoal       = useAchieveGoal()
  const updateGoal        = useUpdateGoal()
  const restartGoal       = useRestartGoal()

  // Открыть bottom sheet прогресса: предзаполнить текущим значением
  const openProgressSheet = () => {
    setProgressValue(goal?.progress_pct ?? 0)
    setProgressNote('')
    setOfferAchieve(false)
    setShowProgressSheet(true)
  }

  // Сохранить прогресс
  const handleSaveProgress = () => {
    updateGoal.mutate(
      { id: goalId, progress_pct: progressValue, coaching_notes: progressNote || undefined },
      {
        onSuccess: () => {
          setShowProgressSheet(false)
          // Если выставили 100% — предложить отметить как достигнутую
          if (progressValue === 100) setOfferAchieve(true)
        },
      }
    )
  }

  // Добавить этап
  const handleAddMilestone = () => {
    if (!newMilestoneTitle.trim()) return
    createMilestone.mutate(
      {
        goal_id:     goalId,
        title:       newMilestoneTitle.trim(),
        due_date:    newMilestoneDue || undefined,
        order_index: milestones.length,
      },
      {
        onSuccess: () => {
          setNewMilestoneTitle('')
          setNewMilestoneDue('')
          setShowAddMilestone(false)
        },
      }
    )
  }

  // Прокрутить к форме добавления этапа и раскрыть её
  const scrollToMilestoneForm = () => {
    setShowAddMilestone(true)
    setTimeout(() => {
      milestoneFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 100)
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-full">
        <Loader2 className="animate-spin" size={30} style={{ color: '#818cf8' }} />
      </div>
    )
  }
  if (!goal) {
    return (
      <div className="flex justify-center items-center h-full">
        <p style={{ color: 'var(--app-hint)' }}>Цель не найдена</p>
      </div>
    )
  }

  const pct        = Math.round(goal.progress_pct ?? 0)
  const deadline   = deadlineInfo(goal.target_date ?? null)
  const areaEmoji  = AREA_EMOJI[goal.area ?? ''] ?? '🎯'
  const areaLabel  = AREA_LABEL[goal.area ?? ''] ?? (goal.area ?? '')
  const isActive   = goal.status === 'active' && !goal.is_frozen
  const isFrozen   = goal.is_frozen
  // Перезапуск доступен если цель заморожена или уже есть прогресс
  const canRestart = isFrozen || pct > 0

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* ── Шапка ─────────────────────────────────────────────────── */}
      <div className="px-4 pt-6 pb-3 shrink-0">
        {/* Строка: кнопка назад + название */}
        <div className="flex items-center gap-3 mb-3">
          <button
            onClick={() => navigate('/coaching/goals')}
            className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
            style={{ background: 'rgba(255,255,255,0.06)' }}
          >
            <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
          </button>
          <h1 className="text-lg font-black flex-1 leading-snug" style={{ color: 'var(--app-text)' }}>
            {goal.title}
          </h1>
        </div>

        {/* Область + статус-бейдж */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          {goal.area && (
            <span className="text-sm" style={{ color: 'var(--app-hint)' }}>
              {areaEmoji} {areaLabel}
            </span>
          )}
          <StatusBadge goal={goal} />
        </div>

        {/* Дедлайн с цветом */}
        {deadline && (
          <div className="flex items-center gap-1.5">
            <Calendar size={13} style={{ color: deadline.color }} />
            <span className="text-xs font-medium" style={{ color: deadline.color }}>
              {deadline.label}
            </span>
          </div>
        )}

        {/* Плашка заморозки */}
        {goal.is_frozen && goal.frozen_reason && (
          <div
            className="mt-2 px-3 py-2 rounded-xl text-xs"
            style={{
              background: 'rgba(148,163,184,0.08)',
              color: '#94a3b8',
              border: '1px solid rgba(148,163,184,0.18)',
            }}
          >
            ❄️ Заморожена: {goal.frozen_reason}
          </div>
        )}
      </div>

      {/* ── Скролл-контент ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 pb-36 space-y-4">

        {/* Зачем мне это */}
        {goal.why_statement && (
          <GlassCard>
            <p className="text-xs uppercase tracking-wide mb-1" style={{ color: 'var(--app-hint)' }}>
              Зачем мне это
            </p>
            <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>
              {goal.why_statement}
            </p>
          </GlassCard>
        )}

        {/* Первый шаг */}
        {goal.first_step && (
          <GlassCard>
            <div className="flex items-start gap-2">
              <span className="text-lg shrink-0">🚀</span>
              <div>
                <p className="text-xs uppercase tracking-wide mb-0.5" style={{ color: 'var(--app-hint)' }}>
                  Первый шаг
                </p>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>
                  {goal.first_step}
                </p>
              </div>
            </div>
          </GlassCard>
        )}

        {/* Прогресс */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold" style={{ color: 'var(--app-hint)' }}>Прогресс</span>
            <span className="text-2xl font-black" style={{ color: '#818cf8' }}>{pct}%</span>
          </div>
          <div className="h-2.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="h-full rounded-full"
              style={{ background: 'linear-gradient(90deg, #6366f1, #8b5cf6)' }}
            />
          </div>
          <p className="text-xs mt-2" style={{ color: 'var(--app-hint)' }}>
            {goal.milestones_completed ?? 0} из {goal.milestones_total ?? milestones.length} этапов
          </p>
        </GlassCard>

        {/* ── Этапы — воронка ──────────────────────────────────────── */}
        <GlassCard>
          <p className="text-sm font-semibold mb-3" style={{ color: 'var(--app-text)' }}>Этапы</p>

          {milestones.length === 0 && !showAddMilestone ? (
            /* Пустое состояние: подсказка из архитектуры §12.2 */
            <div
              className="rounded-xl p-4 text-center"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px dashed rgba(255,255,255,0.1)' }}
            >
              <p className="text-sm mb-2" style={{ color: 'var(--app-hint)' }}>
                💡 Разбей цель на этапы — без промежуточных точек мозг откладывает
              </p>
              <button
                onClick={() => setShowAddMilestone(true)}
                className="text-xs font-semibold px-4 py-2 rounded-lg"
                style={{ background: 'rgba(99,102,241,0.2)', color: '#818cf8' }}
              >
                Добавить первый этап
              </button>
            </div>
          ) : (
            /* Список этапов с нумерацией */
            <div className="space-y-0">
              {milestones.map((m, idx) => {
                const mDeadline = m.due_date ? deadlineInfo(m.due_date) : null
                const isDone    = m.status === 'done'
                return (
                  <div key={m.id} className="flex items-start gap-3">
                    {/* Кружок с номером + вертикальная линия */}
                    <div className="flex flex-col items-center shrink-0 mt-1">
                      <div
                        className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
                        style={{
                          background: isDone ? 'rgba(74,222,128,0.2)' : 'rgba(255,255,255,0.08)',
                          color:      isDone ? '#4ade80' : 'var(--app-hint)',
                          border:     isDone ? '1px solid rgba(74,222,128,0.3)' : '1px solid rgba(255,255,255,0.1)',
                        }}
                      >
                        {isDone ? '✓' : idx + 1}
                      </div>
                      {idx < milestones.length - 1 && (
                        <div
                          className="w-px"
                          style={{ height: 24, background: 'rgba(255,255,255,0.07)', marginTop: 2 }}
                        />
                      )}
                    </div>

                    {/* Контент этапа — нажатие завершает его */}
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      onClick={() => !isDone && completeMilestone.mutate(m.id)}
                      className="flex-1 pb-4 text-left"
                      style={{ background: 'transparent' }}
                    >
                      <span
                        className="text-sm block"
                        style={{
                          color:          isDone ? 'var(--app-hint)' : 'var(--app-text)',
                          textDecoration: isDone ? 'line-through'    : 'none',
                        }}
                      >
                        {m.title}
                      </span>
                      {/* Дата и вклад этапа в общий прогресс */}
                      <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                        {mDeadline && (
                          <span
                            className="text-xs flex items-center gap-1"
                            style={{ color: isDone ? 'var(--app-hint)' : mDeadline.color }}
                          >
                            <Clock size={10} />
                            {isDone
                              ? (m.completed_at
                                  ? new Date(m.completed_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                                  : 'выполнено')
                              : mDeadline.label
                            }
                          </span>
                        )}
                        {milestones.length > 0 && (
                          <span className="text-xs" style={{ color: 'rgba(255,255,255,0.18)' }}>
                            {Math.round(100 / milestones.length)}% цели
                          </span>
                        )}
                      </div>
                    </motion.button>
                  </div>
                )
              })}
            </div>
          )}

          {/* Inline-форма добавления нового этапа */}
          <AnimatePresence>
            {showAddMilestone && (
              <motion.div
                ref={milestoneFormRef}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-3 space-y-2 overflow-hidden"
              >
                <input
                  type="text"
                  placeholder="Название этапа"
                  value={newMilestoneTitle}
                  onChange={e => setNewMilestoneTitle(e.target.value)}
                  className="w-full rounded-xl px-3 py-2 text-sm outline-none"
                  style={{
                    background: 'rgba(255,255,255,0.06)',
                    border:     '1px solid rgba(255,255,255,0.1)',
                    color:      'var(--app-text)',
                  }}
                  autoFocus
                />
                <div className="flex gap-2">
                  <input
                    type="date"
                    value={newMilestoneDue}
                    onChange={e => setNewMilestoneDue(e.target.value)}
                    className="flex-1 rounded-xl px-3 py-2 text-sm outline-none"
                    style={{
                      background: 'rgba(255,255,255,0.06)',
                      border:     '1px solid rgba(255,255,255,0.1)',
                      color:      newMilestoneDue ? 'var(--app-text)' : 'var(--app-hint)',
                    }}
                  />
                  <button
                    onClick={handleAddMilestone}
                    disabled={!newMilestoneTitle.trim() || createMilestone.isPending}
                    className="px-4 py-2 rounded-xl text-sm font-semibold shrink-0"
                    style={{
                      background: 'rgba(99,102,241,0.3)',
                      color:   '#818cf8',
                      opacity: !newMilestoneTitle.trim() ? 0.5 : 1,
                    }}
                  >
                    {createMilestone.isPending
                      ? <Loader2 size={14} className="animate-spin" />
                      : 'Добавить'
                    }
                  </button>
                  <button
                    onClick={() => setShowAddMilestone(false)}
                    className="px-3 py-2 rounded-xl text-sm shrink-0"
                    style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
                  >
                    <X size={14} />
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Кнопка «+ Добавить этап» (если этапы уже есть) */}
          {milestones.length > 0 && !showAddMilestone && (
            <button
              onClick={() => setShowAddMilestone(true)}
              className="mt-3 flex items-center gap-1.5 text-xs font-medium"
              style={{ color: 'rgba(129,140,248,0.7)' }}
            >
              <Plus size={13} /> Добавить этап
            </button>
          )}
        </GlassCard>

        {/* ── Привязанные привычки ─────────────────────────────────── */}
        <GlassCard>
          <p className="text-sm font-semibold mb-3" style={{ color: 'var(--app-text)' }}>
            Привязанные привычки
          </p>
          {habits.length === 0 ? (
            <p className="text-xs leading-relaxed" style={{ color: 'var(--app-hint)' }}>
              Нет привязанных привычек. Создай привычку, поддерживающую эту цель — ежедневные действия ускоряют движение к результату.
            </p>
          ) : (
            <div className="space-y-2">
              {habits.map(h => (
                <div key={h.id} className="flex items-center gap-3 py-1">
                  <span className="text-base shrink-0">{h.emoji ?? AREA_EMOJI[h.area ?? ''] ?? '✨'}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate" style={{ color: 'var(--app-text)' }}>{h.title}</p>
                    <p className="text-xs" style={{ color: 'var(--app-hint)' }}>🔥 {h.current_streak} дней</p>
                  </div>
                  {/* Статус сегодня */}
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center text-sm shrink-0"
                    style={{
                      background: h.today_done ? 'rgba(74,222,128,0.15)' : 'rgba(255,255,255,0.06)',
                      color:      h.today_done ? '#4ade80'               : 'var(--app-hint)',
                    }}
                  >
                    {h.today_done ? '✓' : '○'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </GlassCard>

        {/* ── История чекинов ──────────────────────────────────────── */}
        {history.length > 0 && (
          <GlassCard>
            <p className="text-sm font-semibold mb-3" style={{ color: 'var(--app-text)' }}>
              Последние чекины
            </p>
            <div className="space-y-2">
              {history.slice(0, 5).map(c => (
                <div key={c.id} className="flex items-start gap-3 py-1">
                  <div className="flex flex-col items-center gap-1">
                    <span className="text-base">
                      {'⚡'.repeat(Math.min(Math.round((c.energy_level ?? 0) / 2), 5))}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
                      {c.energy_level ?? '-'}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs truncate" style={{ color: 'var(--app-hint)' }}>
                      {c.notes?.slice(0, 80) ?? '—'}
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.2)' }}>
                      {new Date(c.created_at).toLocaleDateString('ru-RU')}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        {/* AI-инсайт */}
        {goal.ai_insight && <CoachPromptBubble text={goal.ai_insight} />}

        {/* Предложение отметить как достигнутую после прогресса 100% */}
        <AnimatePresence>
          {offerAchieve && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
            >
              <GlassCard>
                <p className="text-sm font-semibold mb-1" style={{ color: '#4ade80' }}>🎉 Прогресс 100%!</p>
                <p className="text-xs mb-3" style={{ color: 'var(--app-hint)' }}>
                  Отметить цель как достигнутую?
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => { achieveGoal.mutate(goalId); setOfferAchieve(false) }}
                    className="flex-1 py-2 rounded-xl text-sm font-semibold"
                    style={{ background: 'rgba(74,222,128,0.2)', color: '#4ade80' }}
                  >
                    ✅ Да, достигнута!
                  </button>
                  <button
                    onClick={() => setOfferAchieve(false)}
                    className="px-4 py-2 rounded-xl text-sm"
                    style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
                  >
                    Позже
                  </button>
                </div>
              </GlassCard>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ══════════════════════════════════════════════════════════════
          Sticky-панель действий
      ══════════════════════════════════════════════════════════════ */}
      <div
        className="fixed bottom-0 inset-x-0 px-4 py-3 shrink-0"
        style={{ background: 'var(--app-bg)', borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        {goal.status === 'achieved' ? (
          /* Цель достигнута — заглушка */
          <p className="text-center text-sm font-semibold py-1" style={{ color: '#4ade80' }}>
            ✅ Цель достигнута!
          </p>
        ) : (
          <div className="flex gap-2">
            {/* 📈 Обновить прогресс */}
            <button
              onClick={openProgressSheet}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-medium"
              style={{
                background: 'rgba(99,102,241,0.2)',
                color:      '#818cf8',
                border:     '1px solid rgba(99,102,241,0.3)',
              }}
            >
              <TrendingUp size={15} /> Прогресс
            </button>

            {/* ➕ Добавить этап */}
            <button
              onClick={scrollToMilestoneForm}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-xl py-3 text-sm font-medium border border-white/[0.08]"
              style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
            >
              <Plus size={15} /> Этап
            </button>

            {/* ⋯ Ещё (Заморозить / Возобновить / Перезапустить / Достигнуто) */}
            <button
              onClick={() => setShowMoreMenu(true)}
              className="w-12 flex items-center justify-center rounded-xl py-3 border border-white/[0.08] shrink-0"
              style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
            >
              <MoreHorizontal size={18} />
            </button>
          </div>
        )}
      </div>

      {/* ══════════════════════════════════════════════════════════════
          Bottom sheet: меню «Ещё»
      ══════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {showMoreMenu && (
          <>
            {/* Затемнение */}
            <motion.div
              className="fixed inset-0 z-40"
              style={{ background: 'rgba(0,0,0,0.5)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowMoreMenu(false)}
            />
            {/* Шторка */}
            <motion.div
              className="fixed bottom-0 inset-x-0 z-50 rounded-t-2xl px-4 pt-4 pb-8"
              style={{ background: 'var(--app-card-bg, #1e1e2e)', border: '1px solid rgba(255,255,255,0.08)' }}
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            >
              {/* Индикатор */}
              <div className="w-10 h-1 rounded-full mx-auto mb-4" style={{ background: 'rgba(255,255,255,0.15)' }} />

              <div className="space-y-2">
                {/* 🔄 Перезапустить */}
                {canRestart && (
                  <button
                    onClick={() => { setShowMoreMenu(false); setConfirmRestart(true) }}
                    className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-left"
                    style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
                  >
                    <RotateCcw size={16} /> Перезапустить (сбросить прогресс)
                  </button>
                )}
                {/* ❄️ Заморозить */}
                {isActive && (
                  <button
                    onClick={() => { setShowMoreMenu(false); freezeGoal.mutate(goalId) }}
                    className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium text-left"
                    style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
                  >
                    <Snowflake size={16} /> Заморозить
                  </button>
                )}
                {/* ▶️ Возобновить */}
                {isFrozen && (
                  <button
                    onClick={() => { setShowMoreMenu(false); resumeGoal.mutate(goalId) }}
                    className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold text-left"
                    style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
                  >
                    <PlayCircle size={16} /> Возобновить
                  </button>
                )}
                {/* 🏆 Достигнуто */}
                {(isActive || isFrozen) && (
                  <button
                    onClick={() => { setShowMoreMenu(false); achieveGoal.mutate(goalId) }}
                    className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-semibold text-left"
                    style={{
                      background: 'rgba(34,197,94,0.15)',
                      color:      '#4ade80',
                      border:     '1px solid rgba(34,197,94,0.2)',
                    }}
                  >
                    <Trophy size={16} /> Цель достигнута!
                  </button>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ══════════════════════════════════════════════════════════════
          Диалог подтверждения перезапуска
      ══════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {confirmRestart && (
          <>
            <motion.div
              className="fixed inset-0 z-40"
              style={{ background: 'rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setConfirmRestart(false)}
            />
            <motion.div
              className="fixed bottom-0 inset-x-0 z-50 rounded-t-2xl px-4 pt-6 pb-10"
              style={{ background: 'var(--app-card-bg, #1e1e2e)', border: '1px solid rgba(255,255,255,0.08)' }}
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            >
              <p className="text-base font-bold mb-2" style={{ color: 'var(--app-text)' }}>
                Перезапустить цель?
              </p>
              <p className="text-sm mb-5" style={{ color: 'var(--app-hint)' }}>
                Прогресс будет сброшен до 0%. Этапы и история чекинов останутся.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setConfirmRestart(false)}
                  className="flex-1 py-3 rounded-xl text-sm font-medium border border-white/[0.08]"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}
                >
                  Отмена
                </button>
                <button
                  onClick={() => { restartGoal.mutate(goalId); setConfirmRestart(false) }}
                  className="flex-1 py-3 rounded-xl text-sm font-semibold"
                  style={{
                    background: 'rgba(248,113,113,0.2)',
                    color:      '#f87171',
                    border:     '1px solid rgba(248,113,113,0.3)',
                  }}
                >
                  🔄 Перезапустить
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ══════════════════════════════════════════════════════════════
          Bottom sheet: Обновить прогресс
      ══════════════════════════════════════════════════════════════ */}
      <AnimatePresence>
        {showProgressSheet && (
          <>
            <motion.div
              className="fixed inset-0 z-40"
              style={{ background: 'rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setShowProgressSheet(false)}
            />
            <motion.div
              className="fixed bottom-0 inset-x-0 z-50 rounded-t-2xl px-4 pt-6 pb-10"
              style={{ background: 'var(--app-card-bg, #1e1e2e)', border: '1px solid rgba(255,255,255,0.08)' }}
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
            >
              {/* Ручка шторки */}
              <div className="w-10 h-1 rounded-full mx-auto mb-5" style={{ background: 'rgba(255,255,255,0.15)' }} />

              <p className="text-base font-bold mb-4" style={{ color: 'var(--app-text)' }}>
                Обновить прогресс
              </p>

              {/* Текущее значение */}
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm" style={{ color: 'var(--app-hint)' }}>Прогресс по цели</span>
                <span className="text-2xl font-black" style={{ color: '#818cf8' }}>{progressValue}%</span>
              </div>

              {/* Слайдер */}
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={progressValue}
                onChange={e => setProgressValue(Number(e.target.value))}
                className="w-full mb-2 accent-indigo-500"
              />

              {/* Шкала */}
              <div className="flex justify-between text-xs mb-4" style={{ color: 'rgba(255,255,255,0.2)' }}>
                <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
              </div>

              {/* Заметка */}
              <textarea
                placeholder="Что сдвинулось? Что мешает? (опционально)"
                value={progressNote}
                onChange={e => setProgressNote(e.target.value)}
                rows={3}
                className="w-full rounded-xl px-3 py-2.5 text-sm outline-none resize-none mb-4"
                style={{
                  background: 'rgba(255,255,255,0.06)',
                  border:     '1px solid rgba(255,255,255,0.1)',
                  color:      'var(--app-text)',
                }}
              />

              {/* Сохранить */}
              <button
                onClick={handleSaveProgress}
                disabled={updateGoal.isPending}
                className="w-full py-3 rounded-xl text-sm font-semibold"
                style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
              >
                {updateGoal.isPending
                  ? <Loader2 size={16} className="animate-spin mx-auto" />
                  : '📈 Сохранить прогресс'
                }
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

    </div>
  )
}
