/**
 * CoachingDashboard — главный экран модуля коучинга.
 *
 * Рефакторинг §13.1: приведение информационной иерархии в соответствие с
 * docs/coaching-architecture.md:
 *  1. State Card — sticky, адаптивный (эмодзи/градиент по состоянию), фокус дня, 3 Quick Actions внутри
 *  2. Удалён 6-кнопочный grid навигации
 *  3. Habits Today — горизонтальный strip с прогрессом X/Y, 1-tap логирование
 *  4. AI Insight Card — после секции Goals, GlassCard с severity-цветом
 *  5. Weekly Score — отдельная секция в конце дашборда
 *  6. Nudge Pending — коллапсируемый баннер под State Card
 *  7. CoachPromptBubble — только в пустых состояниях
 *  8. Prompt suggestions — горизонтальные чипы-шорткаты для Telegram-чата
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Loader2, ChevronRight, Plus,
  CheckCircle, XCircle, Sparkles,
  Bell, X, BarChart2, AlertCircle,
} from 'lucide-react'
import {
  useDashboard,
  useLogHabit,
  useMissHabit,
  useDismissRecommendation,
  useMarkInsightRead,
  type CoachingState,
} from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'
import { GoalCard } from './components/GoalCard'
import { CoachPromptBubble } from './components/CoachPromptBubble'

// ── Конфигурация состояний пользователя (тёмная тема) ─────────────────────────
// Соответствует §16.1: momentum / stable / overload / recovery / risk
const STATE_CFG: Record<CoachingState, {
  emoji: string
  label: string
  gradient: string   // фон карточки
  accent: string     // цвет акцентного текста
  bar: string        // цвет прогресс-бара
}> = {
  momentum: {
    emoji:    '🔥',
    label:    'Momentum',
    gradient: 'linear-gradient(135deg, rgba(99,102,241,0.28), rgba(139,92,246,0.18))',
    accent:   '#a5b4fc',
    bar:      '#6366f1',
  },
  stable: {
    emoji:    '⚖️',
    label:    'Стабильно',
    gradient: 'linear-gradient(135deg, rgba(34,197,94,0.22), rgba(16,185,129,0.12))',
    accent:   '#4ade80',
    bar:      '#22c55e',
  },
  overload: {
    emoji:    '😮',
    label:    'Перегруз',
    gradient: 'linear-gradient(135deg, rgba(249,115,22,0.28), rgba(239,68,68,0.18))',
    accent:   '#fb923c',
    bar:      '#f97316',
  },
  recovery: {
    emoji:    '🔄',
    label:    'Восстановление',
    gradient: 'linear-gradient(135deg, rgba(6,182,212,0.22), rgba(59,130,246,0.12))',
    accent:   '#67e8f9',
    bar:      '#06b6d4',
  },
  risk: {
    emoji:    '⚠️',
    label:    'Зона риска',
    gradient: 'linear-gradient(135deg, rgba(239,68,68,0.28), rgba(220,38,38,0.18))',
    accent:   '#f87171',
    bar:      '#ef4444',
  },
}

// Эмодзи привычки по области (если emoji не передан в данных)
const AREA_EMOJI: Record<string, string> = {
  health:       '💪',
  sport:        '🏃',
  mindset:      '🧠',
  productivity: '⚡',
  nutrition:    '🥗',
  study:        '📚',
}

// Цвет weekly_score: зелёный ≥70, жёлтый ≥40, красный <40
function scoreColor(score: number): string {
  if (score >= 70) return '#4ade80'
  if (score >= 40) return '#fbbf24'
  return '#f87171'
}

// Цвет рамки AI-инсайта по severity
function insightBorderColor(severity: string): string {
  if (severity === 'critical') return 'rgba(239,68,68,0.5)'
  if (severity === 'warning')  return 'rgba(249,115,22,0.4)'
  return 'rgba(99,102,241,0.35)'
}

// ── Открыть Telegram-чат (закрыть Mini App) ────────────────────────────────
function openTelegramChat() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(window as any).Telegram?.WebApp?.close()
}

// ─────────────────────────────────────────────────────────────────────────────

export function CoachingDashboard() {
  const navigate   = useNavigate()
  const { data: dash, isLoading } = useDashboard()
  const logHabit   = useLogHabit()
  const missHabit  = useMissHabit()
  const dismissRec = useDismissRecommendation()
  const markRead   = useMarkInsightRead()

  // Локальное состояние: скрыт ли nudge-баннер пользователем
  const [nudgeDismissed, setNudgeDismissed] = useState(false)

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="animate-spin" size={32} style={{ color: '#818cf8' }} />
      </div>
    )
  }

  // ── Нет данных → экран онбординга (§13.2) ─────────────────────────────────
  if (!dash) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-5 px-8 text-center">
        <div
          className="w-20 h-20 rounded-full flex items-center justify-center text-3xl"
          style={{ background: 'rgba(99,102,241,0.1)' }}
        >
          🧭
        </div>
        <div>
          <p className="text-base font-bold mb-1" style={{ color: 'var(--app-text)' }}>
            Начни с коучем
          </p>
          <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
            Ставь цели, отслеживай привычки, получай AI-инсайты
          </p>
        </div>
        {/* 3 CTA по §13.2 */}
        <div className="flex flex-col gap-2 w-full">
          <button
            onClick={() => navigate('/coaching/goals')}
            className="py-3 rounded-2xl font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            🎯 Поставить первую цель
          </button>
          <button
            onClick={() => navigate('/coaching/habits')}
            className="py-3 rounded-2xl font-semibold"
            style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-text)' }}
          >
            🔄 Создать привычку
          </button>
          <button
            onClick={() => navigate('/coaching/onboarding')}
            className="py-3 rounded-2xl font-semibold"
            style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--app-hint)' }}
          >
            ❓ Как это работает
          </button>
        </div>
        {/* Подсказка для Telegram-чата в пустом состоянии */}
        <CoachPromptBubble
          text='Напиши мне в чат: "Помоги поставить цель на месяц"'
          action="Открыть чат"
          onAction={openTelegramChat}
        />
      </div>
    )
  }

  // ── Вычисляемые данные ────────────────────────────────────────────────────
  const stateCfg   = STATE_CFG[dash.state] ?? STATE_CFG.stable
  const hasGoals   = (dash.goals_active?.length ?? 0) > 0
  const hasHabits  = (dash.habits_today?.length ?? 0) > 0
  const hasInsight = !!dash.top_insight?.body
  const hasRecs    = (dash.recommendations?.length ?? 0) > 0
  const hasNudge   = !!dash.nudge_pending && !nudgeDismissed
  const hasSuggestions = (dash.prompt_suggestions?.length ?? 0) > 0

  // Фокус дня — первая активная цель (§13.1: «главный фокус дня»)
  const focusGoal = dash.goals_active?.[0]

  // Счётчик привычек за сегодня
  const habitsDone  = dash.habits_today?.filter(h => h.today_done === true).length ?? 0
  const habitsTotal = dash.habits_today?.length ?? 0

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* ── Шапка ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>Коучинг</h1>
          <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
            {new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
          </p>
        </div>
        {/* Кнопка перехода на страницу инсайтов */}
        <button
          onClick={() => navigate('/coaching/insights')}
          className="p-2 rounded-xl"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <Sparkles size={20} style={{ color: 'var(--app-hint)' }} />
        </button>
      </div>

      {/* ── Скролл-область ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto pb-24">

        {/* ═══════════════════════════════════════════════════════════════════
            1. DAILY STATE CARD — sticky, адаптивная (§13.1 + §16.2)
            Содержит: режим + score + прогресс-бар + фокус дня + 3 Quick Actions
        ════════════════════════════════════════════════════════════════════ */}
        <div
          className="sticky top-0 z-10 px-4 pb-3"
          style={{ background: 'var(--app-bg, #0f0f13)' }}
        >
          <div
            className="rounded-2xl p-4 border border-white/[0.08]"
            style={{ background: stateCfg.gradient }}
          >
            {/* Строка: эмодзи + лейбл состояния + score */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-2xl">{stateCfg.emoji}</span>
                <div>
                  <p
                    className="text-[10px] font-semibold uppercase tracking-wide"
                    style={{ color: stateCfg.accent }}
                  >
                    Твоё состояние
                  </p>
                  <p className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                    {stateCfg.label}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className="text-2xl font-black" style={{ color: 'var(--app-text)' }}>
                  {dash.state_score ?? 0}
                </span>
                <span className="text-xs ml-0.5" style={{ color: 'var(--app-hint)' }}>/100</span>
              </div>
            </div>

            {/* Прогресс-бар состояния */}
            <div className="h-1 rounded-full mb-3" style={{ background: 'rgba(255,255,255,0.1)' }}>
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${dash.state_score ?? 0}%`, background: stateCfg.bar }}
              />
            </div>

            {/* Фокус дня — первая активная цель */}
            {focusGoal && (
              <div
                className="text-xs px-3 py-2 rounded-xl mb-3 truncate"
                style={{ background: 'rgba(0,0,0,0.2)', color: 'var(--app-hint)' }}
              >
                <span style={{ color: stateCfg.accent }}>Фокус: </span>
                {focusGoal.title}
              </div>
            )}

            {/* Quick Actions (§13.1): Check-in / Привычки / Открыть чат */}
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => navigate('/coaching/checkin')}
                className="py-2 rounded-xl text-xs font-semibold"
                style={{ background: 'rgba(0,0,0,0.25)', color: 'var(--app-text)' }}
              >
                ✏️ Чекин
              </button>
              <button
                onClick={() => navigate('/coaching/habits')}
                className="py-2 rounded-xl text-xs font-semibold"
                style={{ background: 'rgba(0,0,0,0.25)', color: 'var(--app-text)' }}
              >
                🔄 Привычки
              </button>
              <button
                onClick={openTelegramChat}
                className="py-2 rounded-xl text-xs font-semibold"
                style={{ background: 'rgba(0,0,0,0.25)', color: 'var(--app-text)' }}
              >
                💬 Чат
              </button>
            </div>
          </div>
        </div>

        <div className="px-4 space-y-4">

          {/* ═══════════════════════════════════════════════════════════════
              2. NUDGE PENDING БАННЕР (§5.4)
              Показывается если есть pending proactive-сообщение от коуча
          ════════════════════════════════════════════════════════════════ */}
          <AnimatePresence>
            {hasNudge && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="rounded-2xl p-3 flex items-start gap-3 border"
                style={{
                  background:   'rgba(251,191,36,0.08)',
                  borderColor:  'rgba(251,191,36,0.25)',
                }}
              >
                <Bell size={16} style={{ color: '#fbbf24', marginTop: 1, flexShrink: 0 }} />
                <p className="flex-1 text-xs leading-relaxed" style={{ color: 'var(--app-text)' }}>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {(dash.nudge_pending as any).content_preview ?? 'Есть сообщение от коуча'}
                </p>
                <button onClick={() => setNudgeDismissed(true)}>
                  <X size={14} style={{ color: 'var(--app-hint)' }} />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ═══════════════════════════════════════════════════════════════
              3. HABITS TODAY STRIP (§13.1, §13.4)
              Горизонтальный scroll, 1-tap логирование, прогресс X/Y
          ════════════════════════════════════════════════════════════════ */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                Привычки сегодня
                {/* Счётчик прогресса X/Y */}
                {hasHabits && (
                  <span
                    className="ml-2 font-bold"
                    style={{ color: habitsDone === habitsTotal && habitsTotal > 0 ? '#4ade80' : 'var(--app-text)' }}
                  >
                    {habitsDone}/{habitsTotal}
                  </span>
                )}
              </span>
              <button
                onClick={() => navigate('/coaching/habits')}
                className="flex items-center gap-0.5 text-xs"
                style={{ color: '#818cf8' }}
              >
                Все <ChevronRight size={14} />
              </button>
            </div>

            {hasHabits ? (
              /* Горизонтальный скролл-стрип */
              <div
                className="flex gap-3 overflow-x-auto pb-1"
                style={{ scrollbarWidth: 'none' }}
              >
                {dash.habits_today!.map((h) => {
                  // Определяем статус за сегодня
                  const isLogged = h.today_done === true || h.today_done === false
                  // Эмодзи по области или дефолтный
                  const habitEmoji = AREA_EMOJI[h.area ?? ''] ?? '🎯'

                  return (
                    <motion.div
                      key={h.id}
                      whileTap={{ scale: 0.95 }}
                      className="flex-shrink-0 rounded-2xl border border-white/[0.08] p-3 flex flex-col items-center gap-2"
                      style={{
                        width: 96,
                        // Лёгкая заливка при залогированном статусе
                        background: isLogged
                          ? h.today_done
                            ? 'rgba(34,197,94,0.12)'
                            : 'rgba(239,68,68,0.08)'
                          : 'var(--glass-bg)',
                      }}
                    >
                      <span className="text-xl">{habitEmoji}</span>

                      {/* Название привычки (2 строки max) */}
                      <p
                        className="text-[11px] font-medium text-center leading-tight w-full"
                        style={{
                          color: 'var(--app-text)',
                          overflow: 'hidden',
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                        }}
                      >
                        {h.title}
                      </p>

                      {/* Стрик */}
                      {h.current_streak > 0 && (
                        <span className="text-[10px]" style={{ color: '#fb923c' }}>
                          🔥 {h.current_streak}
                        </span>
                      )}

                      {/* Статус или кнопки ✅/❌ */}
                      {isLogged ? (
                        <span className="text-lg">{h.today_done ? '✅' : '❌'}</span>
                      ) : (
                        <div className="flex gap-1.5">
                          <motion.button
                            whileTap={{ scale: 0.8 }}
                            onClick={() => logHabit.mutate(h.id)}
                            className="w-8 h-8 rounded-full flex items-center justify-center"
                            style={{ background: 'rgba(34,197,94,0.15)' }}
                          >
                            <CheckCircle size={16} style={{ color: '#4ade80' }} />
                          </motion.button>
                          <motion.button
                            whileTap={{ scale: 0.8 }}
                            onClick={() => missHabit.mutate(h.id)}
                            className="w-8 h-8 rounded-full flex items-center justify-center"
                            style={{ background: 'rgba(239,68,68,0.12)' }}
                          >
                            <XCircle size={16} style={{ color: '#f87171' }} />
                          </motion.button>
                        </div>
                      )}
                    </motion.div>
                  )
                })}
              </div>
            ) : (
              /* Пустое состояние привычек с CoachPromptBubble (§10.2) */
              <div className="space-y-2">
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={() => navigate('/coaching/habits')}
                  className="w-full rounded-[20px] border border-white/[0.08] p-4 flex items-center justify-between text-left"
                  style={{ background: 'var(--glass-bg)' }}
                >
                  <div>
                    <p className="text-sm font-semibold" style={{ color: 'var(--app-text)' }}>
                      Нет привычек
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--app-hint)' }}>
                      Добавь первую и начни стрик
                    </p>
                  </div>
                  <div
                    className="w-8 h-8 rounded-xl flex items-center justify-center"
                    style={{ background: 'rgba(168,85,247,0.15)' }}
                  >
                    <Plus size={16} style={{ color: '#c084fc' }} />
                  </div>
                </motion.button>
                <CoachPromptBubble
                  text='Напиши: "Создай привычку пить воду каждый день"'
                  action="Открыть чат"
                  onAction={openTelegramChat}
                />
              </div>
            )}
          </div>

          {/* ═══════════════════════════════════════════════════════════════
              4. АКТИВНЫЕ ЦЕЛИ (§13.1, §13.3)
              До 3 карточек, тап → GoalDetailPage
          ════════════════════════════════════════════════════════════════ */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                Мои цели
              </span>
              <button
                onClick={() => navigate('/coaching/goals')}
                className="flex items-center gap-0.5 text-xs"
                style={{ color: '#818cf8' }}
              >
                Все <ChevronRight size={14} />
              </button>
            </div>

            {hasGoals ? (
              <div className="space-y-2">
                {dash.goals_active!.slice(0, 3).map((g) => (
                  <GoalCard
                    key={g.id}
                    goal={g as any}
                    compact
                    onClick={() => navigate(`/coaching/goals/${g.id}`)}
                  />
                ))}
              </div>
            ) : (
              /* Пустое состояние целей с CoachPromptBubble (§10.2) */
              <div className="space-y-2">
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  onClick={() => navigate('/coaching/goals')}
                  className="w-full rounded-[20px] border border-white/[0.08] p-4 flex items-center justify-between text-left"
                  style={{ background: 'var(--glass-bg)' }}
                >
                  <div>
                    <p className="text-sm font-semibold" style={{ color: 'var(--app-text)' }}>
                      Нет активных целей
                    </p>
                    <p className="text-xs mt-0.5" style={{ color: 'var(--app-hint)' }}>
                      Поставь первую цель — дай себе направление
                    </p>
                  </div>
                  <div
                    className="w-8 h-8 rounded-xl flex items-center justify-center"
                    style={{ background: 'rgba(59,130,246,0.15)' }}
                  >
                    <Plus size={16} style={{ color: '#60a5fa' }} />
                  </div>
                </motion.button>
                <CoachPromptBubble
                  text='Напиши: "Помоги поставить цель на месяц"'
                  action="Открыть чат"
                  onAction={openTelegramChat}
                />
              </div>
            )}
          </div>

          {/* ═══════════════════════════════════════════════════════════════
              5. AI INSIGHT CARD (§13.1 — после Goals, §13.7)
              GlassCard с цветом рамки по severity (info/warning/critical)
          ════════════════════════════════════════════════════════════════ */}
          {hasInsight && (
            <GlassCard style={{ borderColor: insightBorderColor(dash.top_insight!.severity) }}>
              <div className="flex items-start gap-3">
                {/* Иконка по severity */}
                <div
                  className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: 'rgba(99,102,241,0.15)' }}
                >
                  {dash.top_insight!.severity === 'critical'
                    ? <AlertCircle size={16} style={{ color: '#f87171' }} />
                    : <Sparkles size={16} style={{ color: '#a5b4fc' }} />
                  }
                </div>

                <div className="flex-1 min-w-0">
                  {/* Заголовок инсайта */}
                  {dash.top_insight!.title && (
                    <p className="text-xs font-semibold mb-0.5" style={{ color: '#a5b4fc' }}>
                      {dash.top_insight!.title}
                    </p>
                  )}
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>
                    {dash.top_insight!.body}
                  </p>
                  {/* Действия: перейти к инсайтам / отметить прочитанным */}
                  <div className="flex items-center justify-between mt-2">
                    <button
                      onClick={() => navigate('/coaching/insights')}
                      className="text-xs"
                      style={{ color: '#818cf8' }}
                    >
                      Все инсайты →
                    </button>
                    <button
                      onClick={() => markRead.mutate(dash.top_insight!.id)}
                      className="text-xs"
                      style={{ color: 'var(--app-hint)' }}
                    >
                      Понятно
                    </button>
                  </div>
                </div>
              </div>
            </GlassCard>
          )}

          {/* ═══════════════════════════════════════════════════════════════
              6. РЕКОМЕНДАЦИИ (§13.1, §17.2 — до 2 карточек)
          ════════════════════════════════════════════════════════════════ */}
          {hasRecs && (
            <div>
              <span className="text-xs font-medium block mb-2" style={{ color: 'var(--app-hint)' }}>
                Рекомендации
              </span>
              <div className="space-y-2">
                {dash.recommendations!.slice(0, 2).map((r) => (
                  <GlassCard key={r.id}>
                    {r.title && (
                      <p className="text-xs font-semibold mb-1" style={{ color: '#a5b4fc' }}>
                        {r.title}
                      </p>
                    )}
                    <p className="text-sm" style={{ color: 'var(--app-text)' }}>{r.body}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                        {r.rec_type}
                      </span>
                      <button
                        onClick={() => dismissRec.mutate(r.id)}
                        className="text-xs"
                        style={{ color: 'var(--app-hint)' }}
                      >
                        Скрыть
                      </button>
                    </div>
                  </GlassCard>
                ))}
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════════
              7. WEEKLY SCORE — отдельная секция (§13.1, §22.3)
              Прогресс-бар + цветной score + переход на WeeklyReviewPage
          ════════════════════════════════════════════════════════════════ */}
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={() => navigate('/coaching/review')}
            className="w-full rounded-2xl border border-white/[0.08] p-4 text-left"
            style={{ background: 'var(--glass-bg)' }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <BarChart2 size={16} style={{ color: '#34d399' }} />
                <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                  Прогресс недели
                </span>
              </div>
              <div className="flex items-center gap-1">
                <span
                  className="text-lg font-black"
                  style={{ color: scoreColor(dash.weekly_score ?? 0) }}
                >
                  {dash.weekly_score ?? 0}
                </span>
                <span className="text-xs" style={{ color: 'var(--app-hint)' }}>/100</span>
                <ChevronRight size={14} style={{ color: 'var(--app-hint)' }} />
              </div>
            </div>
            {/* Прогресс-бар с адаптивным цветом */}
            <div
              className="h-1.5 rounded-full overflow-hidden"
              style={{ background: 'rgba(255,255,255,0.08)' }}
            >
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width:      `${dash.weekly_score ?? 0}%`,
                  background: scoreColor(dash.weekly_score ?? 0),
                }}
              />
            </div>
            <p className="text-[10px] mt-1.5" style={{ color: 'var(--app-hint)' }}>
              Открыть обзор недели →
            </p>
          </motion.button>

          {/* ═══════════════════════════════════════════════════════════════
              8. PROMPT SUGGESTIONS — чипы-шорткаты для чата (§11.7, §13.1)
              Горизонтальный скролл контекстуальных подсказок
          ════════════════════════════════════════════════════════════════ */}
          {hasSuggestions && (
            <div>
              <span className="text-xs font-medium block mb-2" style={{ color: 'var(--app-hint)' }}>
                Попробуй спросить
              </span>
              <div
                className="flex gap-2 overflow-x-auto pb-1"
                style={{ scrollbarWidth: 'none' }}
              >
                {dash.prompt_suggestions!.slice(0, 4).map((prompt, i) => (
                  <button
                    key={i}
                    onClick={openTelegramChat}
                    className="flex-shrink-0 px-3 py-2 rounded-xl text-xs font-medium border border-white/[0.08] whitespace-nowrap"
                    style={{ background: 'rgba(99,102,241,0.1)', color: '#a5b4fc' }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
