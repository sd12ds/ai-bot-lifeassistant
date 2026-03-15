/**
 * GoalsPage — список целей с фильтрами и формой создания.
 *
 * Рефакторинг:
 *  - Убран поиск (бесполезен при ≤10 целях)
 *  - Stats-бар: активные / среднее / достигнуты
 *  - Фильтры со счётчиками
 *  - Hero-карточка пустого состояния
 *  - FAB расширен до pill-кнопки «+ Новая цель»
 *  - ?create=true авто-открывает шторку создания
 */
import { useState, useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Plus, ArrowLeft, Loader2, X, Target, ChevronRight } from "lucide-react"
import { useGoals, useCreateGoal } from "../../api/coaching"
import type { CreateGoalDto } from "../../api/coaching"
import { GoalCard } from "./components/GoalCard"

type Filter = "all" | "active" | "frozen" | "achieved"

// Области жизни (§4.1, §14.1)
const AREAS: { key: string; label: string; emoji: string }[] = [
  { key: "health",        label: "Здоровье",      emoji: "💪" },
  { key: "productivity",  label: "Продуктивность", emoji: "⚡" },
  { key: "career",        label: "Карьера",        emoji: "🚀" },
  { key: "finance",       label: "Финансы",        emoji: "💰" },
  { key: "relationships", label: "Отношения",      emoji: "❤️" },
  { key: "mindset",       label: "Мышление",       emoji: "🧠" },
  { key: "sport",         label: "Спорт",          emoji: "🏃" },
  { key: "personal",      label: "Личное",         emoji: "🌱" },
]

const EMPTY_FORM = { title: "", why: "", area: "", firstStep: "", deadline: "" }

export function GoalsPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [filter, setFilter]           = useState<Filter>("active")
  const [showCreate, setShowCreate]   = useState(false)
  const [form, setForm]               = useState(EMPTY_FORM)
  const [createError, setCreateError] = useState<string | null>(null)

  // Авто-открытие шторки по ?create=true (из дашборда)
  useEffect(() => {
    if (searchParams.get("create") === "true") setShowCreate(true)
  }, [searchParams])

  // Все цели без фильтра — для счётчиков
  const { data: allGoals = [] }          = useGoals(undefined)
  const statusParam                       = filter === "all" ? undefined : filter
  const { data: goals = [], isLoading }  = useGoals(statusParam)
  const createGoal = useCreateGoal()

  // Счётчики для фильтров
  const counts: Record<Filter, number> = {
    all:      allGoals.length,
    active:   allGoals.filter(g => g.status === "active").length,
    frozen:   allGoals.filter(g => g.status === "frozen").length,
    achieved: allGoals.filter(g => g.status === "achieved").length,
  }

  // Stats-данные
  const activeGoals   = allGoals.filter(g => g.status === "active")
  const avgProgress   = activeGoals.length
    ? Math.round(activeGoals.reduce((s, g) => s + (g.progress_pct ?? 0), 0) / activeGoals.length)
    : 0
  const achievedCount = allGoals.filter(g => g.status === "achieved").length

  const closeCreate = () => {
    setShowCreate(false)
    setForm(EMPTY_FORM)
    setCreateError(null)
  }

  const handleCreate = () => {
    setCreateError(null)
    if (!form.title.trim()) return
    const dto: CreateGoalDto = { title: form.title.trim() }
    if (form.why.trim())       dto.why_statement = form.why.trim()
    if (form.area)             dto.area = form.area
    if (form.firstStep.trim()) dto.first_step = form.firstStep.trim()
    if (form.deadline)         dto.target_date = form.deadline
    createGoal.mutate(dto, {
      onSuccess: () => closeCreate(),
      onError:   () => setCreateError("Не удалось создать цель. Попробуй ещё раз."),
    })
  }

  const FILTERS: { key: Filter; label: string }[] = [
    { key: "all",      label: "Все"        },
    { key: "active",   label: "Активные"   },
    { key: "frozen",   label: "Заморожены" },
    { key: "achieved", label: "Достигнуты" },
  ]

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* ── Шапка ─────────────────────────────────────────────────────── */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate("/coaching")}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: "rgba(255,255,255,0.06)" }}
        >
          <ArrowLeft size={20} style={{ color: "var(--app-text)" }} />
        </button>
        <h1 className="text-xl font-black flex-1" style={{ color: "var(--app-text)" }}>
          Мои цели
        </h1>
        {/* Кнопка новой цели в шапке */}
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-3 h-9 rounded-xl text-xs font-semibold shrink-0"
          style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff" }}
        >
          <Plus size={14} />
          Новая
        </button>
      </div>

      {/* ── Stats-бар ─────────────────────────────────────────────────── */}
      {allGoals.length > 0 && (
        <div className="px-4 pb-3 flex gap-2 shrink-0">
          <div
            className="flex-1 px-3 py-2 rounded-xl flex flex-col gap-0.5"
            style={{ background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.2)" }}
          >
            <span className="text-lg font-black" style={{ color: "#818cf8" }}>
              {activeGoals.length}
            </span>
            <span className="text-[10px] font-medium" style={{ color: "rgba(129,140,248,0.7)" }}>
              активных
            </span>
          </div>
          <div
            className="flex-1 px-3 py-2 rounded-xl flex flex-col gap-0.5"
            style={{ background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.18)" }}
          >
            <span className="text-lg font-black" style={{ color: "#fbbf24" }}>
              {avgProgress}%
            </span>
            <span className="text-[10px] font-medium" style={{ color: "rgba(251,191,36,0.7)" }}>
              среднее
            </span>
          </div>
          <div
            className="flex-1 px-3 py-2 rounded-xl flex flex-col gap-0.5"
            style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.18)" }}
          >
            <span className="text-lg font-black" style={{ color: "#4ade80" }}>
              {achievedCount}
            </span>
            <span className="text-[10px] font-medium" style={{ color: "rgba(74,222,128,0.7)" }}>
              достигнуто
            </span>
          </div>
        </div>
      )}

      {/* ── Фильтры со счётчиками ─────────────────────────────────────── */}
      <div className="px-4 pb-4 flex gap-2 overflow-x-auto scrollbar-none shrink-0">
        {FILTERS.map(f => {
          const cnt = counts[f.key]
          const active = filter === f.key
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className="shrink-0 flex items-center gap-1.5 px-4 py-1.5 rounded-full text-sm font-medium transition-all border"
              style={
                active
                  ? { background: "rgba(99,102,241,0.25)", color: "#818cf8", borderColor: "rgba(99,102,241,0.4)" }
                  : { background: "rgba(255,255,255,0.05)", color: "var(--app-hint)", borderColor: "rgba(255,255,255,0.08)" }
              }
            >
              {f.label}
              {cnt > 0 && (
                <span
                  className="text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none"
                  style={{
                    background: active ? "rgba(99,102,241,0.35)" : "rgba(255,255,255,0.1)",
                    color: active ? "#a5b4fc" : "var(--app-hint)",
                  }}
                >
                  {cnt}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* ── Список целей ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 pb-28 space-y-3">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin" size={28} style={{ color: "#818cf8" }} />
          </div>
        ) : goals.length === 0 ? (
          /* ── Hero-карточка пустого состояния ── */
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4"
          >
            <div
              className="rounded-[24px] p-6 flex flex-col items-center text-center"
              style={{
                background: "linear-gradient(145deg, rgba(99,102,241,0.12), rgba(139,92,246,0.06))",
                border: "1px solid rgba(99,102,241,0.2)",
              }}
            >
              <div
                className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
                style={{ background: "rgba(99,102,241,0.15)" }}
              >
                <Target size={30} style={{ color: "#818cf8" }} />
              </div>
              <p className="text-base font-bold mb-1" style={{ color: "var(--app-text)" }}>
                {filter === "achieved" ? "Ещё нет достигнутых целей" :
                 filter === "frozen"   ? "Нет замороженных целей" :
                                         "Поставь первую цель"}
              </p>
              <p className="text-sm mb-5" style={{ color: "var(--app-hint)" }}>
                {filter === "active" || filter === "all"
                  ? "Цель даёт направление и мотивацию. Начни с одной."
                  : "Здесь будут отображаться цели из этой категории"}
              </p>
              {(filter === "active" || filter === "all") && (
                <button
                  onClick={() => setShowCreate(true)}
                  className="flex items-center gap-2 px-6 py-3 rounded-2xl font-semibold text-sm"
                  style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff" }}
                >
                  <Plus size={16} />
                  Поставить цель
                </button>
              )}
            </div>

            {/* Подсказка-баннер "что такое хорошая цель" */}
            {(filter === "active" || filter === "all") && (
              <button
                onClick={() => setShowCreate(true)}
                className="mt-3 w-full rounded-[18px] p-4 flex items-center gap-3 text-left"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
              >
                <span className="text-2xl shrink-0">💡</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold" style={{ color: "var(--app-text)" }}>
                    Совет: SMART-цель
                  </p>
                  <p className="text-[11px] mt-0.5" style={{ color: "var(--app-hint)" }}>
                    Конкретная · Измеримая · Достижимая · Актуальная · Срочная
                  </p>
                </div>
                <ChevronRight size={16} style={{ color: "var(--app-hint)" }} className="shrink-0" />
              </button>
            )}
          </motion.div>
        ) : (
          <AnimatePresence>
            {goals.map((g, i) => (
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

      {/* ── Pill FAB — «+ Новая цель» ────────────────────────────────── */}
      <motion.button
        whileTap={{ scale: 0.94 }}
        onClick={() => setShowCreate(true)}
        className="fixed flex items-center gap-2 px-5 h-12 rounded-full shadow-xl font-semibold text-sm"
        style={{
          background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
          color: "#fff",
          right: "1.25rem",
          bottom: "calc(60px + 1rem)",
          zIndex: 55,
          boxShadow: "0 4px 24px rgba(99,102,241,0.45)",
        }}
      >
        <Plus size={18} />
        Новая цель
      </motion.button>

      {/* ── Шторка создания цели ─────────────────────────────────────── */}
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
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 280 }}
              className="w-full rounded-t-3xl border-t border-white/[0.08]"
              style={{ background: "var(--app-bg)", maxHeight: "90vh", overflowY: "auto" }}
            >
              {/* Sticky заголовок шторки */}
              <div
                className="flex items-center justify-between px-5 pt-5 pb-3 sticky top-0"
                style={{ background: "var(--app-bg)", zIndex: 1 }}
              >
                <h2 className="text-lg font-bold" style={{ color: "var(--app-text)" }}>
                  🎯 Новая цель
                </h2>
                <button
                  onClick={closeCreate}
                  className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{ background: "rgba(255,255,255,0.08)" }}
                >
                  <X size={16} style={{ color: "var(--app-hint)" }} />
                </button>
              </div>

              <div className="px-5 pb-8 space-y-4">

                {/* 1. Название */}
                <div>
                  <label className="text-xs font-semibold mb-1.5 block" style={{ color: "var(--app-hint)" }}>
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
                      background: "rgba(255,255,255,0.06)",
                      color: "var(--app-text)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  />
                </div>

                {/* 2. Область */}
                <div>
                  <label className="text-xs font-semibold mb-2 block" style={{ color: "var(--app-hint)" }}>
                    ОБЛАСТЬ
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {AREAS.map(a => (
                      <button
                        key={a.key}
                        onClick={() => setForm(f => ({ ...f, area: f.area === a.key ? "" : a.key }))}
                        className="flex flex-col items-center gap-1 py-2 px-1 rounded-xl text-xs font-medium transition-all"
                        style={
                          form.area === a.key
                            ? { background: "rgba(99,102,241,0.25)", color: "#a5b4fc", border: "1px solid rgba(99,102,241,0.4)" }
                            : { background: "rgba(255,255,255,0.05)", color: "var(--app-hint)", border: "1px solid rgba(255,255,255,0.07)" }
                        }
                      >
                        <span className="text-base">{a.emoji}</span>
                        <span className="leading-tight text-center" style={{ fontSize: 10 }}>{a.label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* 3. Зачем */}
                <div>
                  <label className="text-xs font-semibold mb-1.5 block" style={{ color: "var(--app-hint)" }}>
                    ЗАЧЕМ МНЕ ЭТО?
                  </label>
                  <textarea
                    placeholder="Чем важна эта цель? Что изменится в жизни..."
                    value={form.why}
                    onChange={e => setForm(f => ({ ...f, why: e.target.value }))}
                    rows={2}
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none resize-none placeholder-white/30"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      color: "var(--app-text)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  />
                </div>

                {/* 4. Первый шаг */}
                <div>
                  <label className="text-xs font-semibold mb-1.5 block" style={{ color: "var(--app-hint)" }}>
                    ПЕРВЫЙ ШАГ
                  </label>
                  <input
                    type="text"
                    placeholder="Конкретное действие, которое можно сделать уже сегодня"
                    value={form.firstStep}
                    onChange={e => setForm(f => ({ ...f, firstStep: e.target.value }))}
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none placeholder-white/30"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      color: "var(--app-text)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  />
                </div>

                {/* 5. Дедлайн */}
                <div>
                  <label className="text-xs font-semibold mb-1.5 block" style={{ color: "var(--app-hint)" }}>
                    ДЕДЛАЙН
                  </label>
                  <input
                    type="date"
                    value={form.deadline}
                    onChange={e => setForm(f => ({ ...f, deadline: e.target.value }))}
                    className="w-full rounded-xl px-4 py-3 text-sm outline-none"
                    style={{
                      background: "rgba(255,255,255,0.06)",
                      color: form.deadline ? "var(--app-text)" : "var(--app-hint)",
                      border: "1px solid rgba(255,255,255,0.1)",
                      colorScheme: "dark",
                    }}
                  />
                </div>

                {createError && (
                  <p className="text-xs text-center" style={{ color: "#f87171" }}>{createError}</p>
                )}

                <button
                  onClick={handleCreate}
                  disabled={!form.title.trim() || createGoal.isPending}
                  className="w-full rounded-2xl py-4 font-bold disabled:opacity-40"
                  style={{ background: "linear-gradient(135deg, #6366f1, #8b5cf6)", color: "#fff" }}
                >
                  {createGoal.isPending ? "Создаём..." : "🎯 Создать цель"}
                </button>

              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
