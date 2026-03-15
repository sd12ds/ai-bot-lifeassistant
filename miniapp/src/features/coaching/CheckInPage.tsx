/**
 * CheckInPage v3 — чекин дня с календарной лентой и слотами времени.
 *
 * Ключевые возможности:
 *  - DayStrip: 15 дней с цветными точками по слотам (утро/день/вечер)
 *  - SlotTabs: переключение между Утром / Днём / Вечером
 *  - Форма зависит от выбранного слота
 *  - Read-only если слот уже заполнен для выбранного дня
 *  - Подсказки о том, когда и зачем заполнять каждый слот
 *  - submit сохраняет time_slot + check_date
 */
import { useState, useMemo, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Sun, Zap, Moon, ChevronDown, HelpCircle } from 'lucide-react'
import {
  useCreateCheckIn,
  useUpdateCheckIn,
  useCheckInByDate,
  useCheckInCalendar,
  useDashboard,
} from '../../api/coaching'
import type { CheckIn, CreateCheckInDto } from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'

// ── Типы ──────────────────────────────────────────────────────────────────────
type SlotType = 'morning' | 'midday' | 'evening'

// ── Утилиты дат ───────────────────────────────────────────────────────────────
const toIso = (d: Date): string => d.toISOString().split('T')[0]

// Генерация последних N дней (сегодня — последний элемент)
function generateDays(count = 15): string[] {
  const today = new Date()
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(today)
    d.setDate(d.getDate() - (count - 1 - i))
    return toIso(d)
  })
}

// Определяем рекомендуемый слот по текущему времени (МСК = UTC+3)
function getDefaultSlot(): SlotType {
  const h = (new Date().getUTCHours() + 3) % 24
  if (h >= 7 && h < 13) return 'morning'
  if (h >= 13 && h < 19) return 'midday'
  return 'evening'
}

// ── Конфиг слотов ─────────────────────────────────────────────────────────────
interface SlotConfig {
  id: SlotType
  label: string
  color: string
  hint: string
}

const SLOTS: SlotConfig[] = [
  {
    id: 'morning',
    label: 'Утро',
    color: '#fbbf24',
    hint: 'Утренний чекин фиксирует твою энергию в начале дня (7–12h). Заполняй каждое утро — так ты отслеживаешь паттерны и понимаешь, в какие дни ты на подъёме.',
  },
  {
    id: 'midday',
    label: 'День',
    color: '#22d3ee',
    hint: 'Дневной пульс (13–17h) — короткая отметка в середине дня. Помогает скорректировать вторую половину: низкая энергия — сделай перерыв, высокая — используй для важных задач.',
  },
  {
    id: 'evening',
    label: 'Вечер',
    color: '#a78bfa',
    hint: 'Вечерняя рефлексия (19–22h) — самый важный слот. Фиксируй настроение, итог дня, победы и блокеры. Именно эти данные бот использует для персональных советов.',
  },
]

const SLOT_ICONS: Record<SlotType, React.ReactNode> = {
  morning: <Sun size={13} />,
  midday: <Zap size={13} />,
  evening: <Moon size={13} />,
}

// ── Шкала эмодзи ──────────────────────────────────────────────────────────────
const ENERGY_EMOJI = ['😴', '😕', '😐', '🙂', '🔥']
const ENERGY_TEXT  = ['Истощён', 'Устал', 'Нейтрально', 'Бодро', 'Горю!']
const MOOD_EMOJI   = ['😢', '😕', '😐', '🙂', '😄']
const MOOD_TEXT    = ['Плохо', 'Грустно', 'Нейтрально', 'Хорошо', 'Отлично!']

// Маппинг строкового mood → число
const MOOD_TO_NUM: Record<string, number> = {
  bad: 1, tired: 2, ok: 3, good: 4, great: 5,
  '1': 1, '2': 2, '3': 3, '4': 4, '5': 5,
}
// Обратный маппинг: число → строковый ключ mood для отправки на бэкенд
const NUM_TO_MOOD: Record<number, string> = {
  1: 'bad', 2: 'tired', 3: 'ok', 4: 'good', 5: 'great',
}

// 5 быстрых кнопок настроения для вечернего слота (§9.3)
const MOOD_QUICK: Array<{ emoji: string; label: string; value: number; color: string }> = [
  { emoji: '🔥', label: 'Продуктивно', value: 5, color: '#f97316' },
  { emoji: '👍', label: 'Норм',         value: 4, color: '#22d3ee' },
  { emoji: '😐', label: 'Так себе',     value: 3, color: '#a78bfa' },
  { emoji: '😔', label: 'Тяжело',       value: 2, color: '#94a3b8' },
  { emoji: '💀', label: 'Провал',       value: 1, color: '#f87171' },
]

// Варианты итога дня для вечернего слота
const DAY_RESULTS: Array<{ key: string; label: string }> = [
  { key: 'great', label: '🔥 Продуктивный' },
  { key: 'ok',    label: '👍 Нормально' },
  { key: 'hard',  label: '😔 Тяжёлый' },
  { key: 'mixed', label: '⚡ Неоднозначно' },
]

// ── ScaleSelector ─────────────────────────────────────────────────────────────
function ScaleSelector({
  value, onChange, emojis, texts, color = '#818cf8',
}: {
  value: number
  onChange: (v: number) => void
  emojis: string[]
  texts: string[]
  color?: string
}) {
  return (
    <div>
      <div className="flex gap-2 justify-between">
        {[1, 2, 3, 4, 5].map(n => (
          <motion.button
            key={n}
            whileTap={{ scale: 0.82 }}
            onClick={() => onChange(n)}
            className="flex-1 aspect-square rounded-xl text-2xl flex items-center justify-center transition-all"
            style={
              value === n
                ? { background: `${color}30`, border: `1.5px solid ${color}80` }
                : { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }
            }
          >
            {emojis[n - 1]}
          </motion.button>
        ))}
      </div>
      <p className="text-center text-xs mt-2 font-medium" style={{ color }}>
        {texts[value - 1]}
      </p>
    </div>
  )
}

// ── DayStrip ──────────────────────────────────────────────────────────────────
function DayStrip({
  days, selectedDate, onSelect, calendarData,
}: {
  days: string[]
  selectedDate: string
  onSelect: (d: string) => void
  calendarData: Record<string, string[]>
}) {
  const today = toIso(new Date())
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const idx = days.indexOf(today)
    const cellW = 52
    el.scrollLeft = Math.max(0, idx * cellW - el.clientWidth / 2 + cellW / 2)
  }, [days, today])

  const DOT_COLORS: Record<string, string> = {
    morning: '#fbbf24',
    midday: '#22d3ee',
    evening: '#a78bfa',
  }

  return (
    <div
      ref={scrollRef}
      className="flex gap-1.5 overflow-x-auto pb-1"
      style={{ scrollbarWidth: 'none' }}
    >
      {days.map(dateStr => {
        const d = new Date(dateStr + 'T00:00:00')
        const isToday = dateStr === today
        const isSelected = dateStr === selectedDate
        const slots = calendarData[dateStr] ?? []

        return (
          <motion.button
            key={dateStr}
            whileTap={{ scale: 0.88 }}
            onClick={() => onSelect(dateStr)}
            className="flex-shrink-0 flex flex-col items-center gap-0.5 py-2 px-2 rounded-xl transition-all"
            style={{
              minWidth: 44,
              background: isSelected
                ? 'rgba(99,102,241,0.22)'
                : isToday
                ? 'rgba(255,255,255,0.06)'
                : 'transparent',
              border: isSelected
                ? '1.5px solid rgba(99,102,241,0.5)'
                : isToday
                ? '1px solid rgba(255,255,255,0.12)'
                : '1px solid transparent',
            }}
          >
            <span
              className="text-[9px] font-medium uppercase"
              style={{ color: isSelected ? '#a5b4fc' : 'var(--app-hint)' }}
            >
              {d.toLocaleDateString('ru', { weekday: 'short' }).slice(0, 2)}
            </span>
            <span
              className="text-sm font-bold"
              style={{
                color: isSelected
                  ? '#c4b5fd'
                  : isToday
                  ? 'var(--app-text)'
                  : 'var(--app-hint)',
              }}
            >
              {d.getDate()}
            </span>
            {/* Цветные точки по заполненным слотам */}
            <div className="flex gap-0.5 items-center">
              {(['morning', 'midday', 'evening'] as SlotType[]).map(slot => (
                <div
                  key={slot}
                  className="rounded-full"
                  style={{
                    width: 4,
                    height: 4,
                    background: slots.includes(slot)
                      ? DOT_COLORS[slot]
                      : 'rgba(255,255,255,0.1)',
                  }}
                />
              ))}
            </div>
          </motion.button>
        )
      })}
    </div>
  )
}

// ── SlotReadonly: отображение уже заполненного слота ──────────────────────────
function SlotReadonly({ checkin, slot, onEdit }: { checkin: CheckIn; slot: SlotType; onEdit: () => void }) {
  const color = SLOTS.find(s => s.id === slot)?.color ?? '#818cf8'
  const moodNum = checkin.mood ? (MOOD_TO_NUM[checkin.mood] ?? null) : null
  const time = new Date(checkin.created_at).toLocaleTimeString('ru', {
    hour: '2-digit', minute: '2-digit',
  })

  return (
    <GlassCard>
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full" style={{ background: color }} />
        <span className="text-xs font-semibold" style={{ color }}>
          Слот заполнен
        </span>
        <span className="ml-auto text-xs" style={{ color: 'var(--app-hint)' }}>
          {time}
        </span>
      </div>

      {checkin.energy_level != null && (
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">{ENERGY_EMOJI[(checkin.energy_level ?? 1) - 1]}</span>
          <div>
            <p className="text-[11px]" style={{ color: 'var(--app-hint)' }}>Энергия</p>
            <p className="text-sm font-semibold" style={{ color: 'var(--app-text)' }}>
              {checkin.energy_level}/5 — {ENERGY_TEXT[(checkin.energy_level ?? 1) - 1]}
            </p>
          </div>
        </div>
      )}

      {moodNum != null && (
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">{MOOD_EMOJI[moodNum - 1]}</span>
          <div>
            <p className="text-[11px]" style={{ color: 'var(--app-hint)' }}>Настроение</p>
            <p className="text-sm font-semibold" style={{ color: 'var(--app-text)' }}>
              {moodNum}/5 — {MOOD_TEXT[moodNum - 1]}
            </p>
          </div>
        </div>
      )}

      {checkin.notes && (
        <div
          className="mt-2 px-3 py-2 rounded-xl"
          style={{ background: 'rgba(255,255,255,0.04)' }}
        >
          <p className="text-[11px] mb-1" style={{ color: 'var(--app-hint)' }}>
            Как прошёл день
          </p>
          <p className="text-sm" style={{ color: 'var(--app-text)' }}>
            {checkin.notes}
          </p>
        </div>
      )}

      {checkin.wins && (
        <div className="mt-2">
          <p className="text-xs">
            <span style={{ color: '#fbbf24' }}>🏆 Победы: </span>
            <span style={{ color: 'var(--app-text)' }}>{checkin.wins}</span>
          </p>
        </div>
      )}

      {checkin.blockers && (
        <div className="mt-1">
          <p className="text-xs">
            <span style={{ color: '#f87171' }}>⚠️ Мешало: </span>
            <span style={{ color: 'var(--app-text)' }}>{checkin.blockers}</span>
          </p>
        </div>
      )}

      {/* Кнопка редактирования */}
      <motion.button
        whileTap={{ scale: 0.96 }}
        onClick={onEdit}
        className="w-full mt-3 py-2.5 rounded-xl text-sm font-semibold"
        style={{
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.1)',
          color: 'var(--app-hint)',
        }}
      >
        ✏️ Изменить
      </motion.button>
    </GlassCard>
  )
}

// ── DaySummaryCard: сводка дня ──────────────────────────────────────────────
function DaySummaryCard({ dayData }: { dayData: Record<string, CheckIn | undefined> }) {
  const morning = dayData.morning
  const midday  = dayData.midday
  const evening = dayData.evening

  const SLOTS_CFG = [
    { id: 'morning', label: 'Утро',  icon: '☀️', color: '#fbbf24', checkin: morning },
    { id: 'midday',  label: 'День',  icon: '⚡', color: '#22d3ee', checkin: midday  },
    { id: 'evening', label: 'Вечер', icon: '🌙', color: '#a78bfa', checkin: evening },
  ]
  const filled  = SLOTS_CFG.filter(s => !!s.checkin).length
  const missing = SLOTS_CFG.filter(s => !s.checkin).map(s => s.label)

  // Средняя энергия за утро+день
  const energies = [morning?.energy_level, midday?.energy_level].filter(Boolean) as number[]
  const avgEnergy = energies.length
    ? Math.round(energies.reduce((a, b) => a + b, 0) / energies.length)
    : null

  // Настроение вечером (числовой код → emoji)
  const eveningMoodNum = evening?.mood ? (MOOD_TO_NUM[evening.mood] ?? null) : null

  return (
    <GlassCard>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
          {filled === 3 ? '✅ День заполнен' : `📊 Сводка · ${filled}/3 слота`}
        </span>
        {avgEnergy && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-lg" style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}>
            ⚡ {ENERGY_TEXT[avgEnergy - 1]}
          </span>
        )}
      </div>
      {/* Три колонки слотов */}
      <div className="flex gap-2 mb-2">
        {SLOTS_CFG.map(s => (
          <div
            key={s.id}
            className="flex-1 flex flex-col items-center gap-1 py-2 rounded-xl"
            style={{
              background: s.checkin ? `${s.color}15` : 'rgba(255,255,255,0.04)',
              border: `1px solid ${s.checkin ? s.color + '35' : 'rgba(255,255,255,0.07)'}`,
            }}
          >
            <span className="text-base">{s.icon}</span>
            <span className="text-[10px] font-medium" style={{ color: s.color }}>{s.label}</span>
            {s.checkin?.energy_level && (
              <span className="text-xs font-bold" style={{ color: s.color }}>{s.checkin.energy_level}/5</span>
            )}
            {s.id === 'evening' && eveningMoodNum && (
              <span className="text-sm">{MOOD_QUICK.find(m => m.value === eveningMoodNum)?.emoji ?? '😐'}</span>
            )}
            {!s.checkin && <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>—</span>}
          </div>
        ))}
      </div>
      {missing.length > 0 && (
        <p className="text-[11px]" style={{ color: 'var(--app-hint)' }}>
          Не заполнено: <span style={{ color: '#a5b4fc' }}>{missing.join(', ')}</span>
        </p>
      )}
      {evening?.notes && (
        <p className="text-xs mt-2 pt-2" style={{ color: 'var(--app-hint)', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <span style={{ color: '#a78bfa' }}>🌙 </span>{evening.notes.slice(0, 80)}{evening.notes.length > 80 ? '...' : ''}
        </p>
      )}
    </GlassCard>
  )
}

// ══ Главный компонент ──────────────────────────────────────────────────────────
export function CheckInPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const today = toIso(new Date())
  const days = useMemo(() => generateDays(15), [])

  // Слот из URL-параметра ?slot=... или авто по времени
  const urlSlot = searchParams.get('slot') as SlotType | null
  const [selectedDate, setSelectedDate] = useState(today)
  const [activeSlot, setActiveSlot] = useState<SlotType>(
    urlSlot && ['morning', 'midday', 'evening'].includes(urlSlot) ? urlSlot : getDefaultSlot()
  )
  const [showHint, setShowHint] = useState(false)

  // Состояние форм
  const [energy, setEnergy] = useState(3)
  const [mood, setMood] = useState(3)
  const [dayResult, setDayResult] = useState('')
  const [notes, setNotes] = useState('')
  const [blockers, setBlockers] = useState('')
  const [wins, setWins] = useState('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isEditMode, setIsEditMode] = useState(false)
  // Привязка к цели (вечерний слот)
  const [selectedGoalId, setSelectedGoalId] = useState<number | null>(null)
  const [progressPct, setProgressPct] = useState(0)
  const [showGoalSelector, setShowGoalSelector] = useState(false)

  const { data: calendarData = {} } = useCheckInCalendar(15)
  const { data: dash } = useDashboard()
  const activeGoals = dash?.goals_active ?? []  // цели для GoalSelector
  const { data: dayData, isLoading } = useCheckInByDate(selectedDate)
  const createCheckIn = useCreateCheckIn()
  const updateCheckIn = useUpdateCheckIn()

  const slotInfo = SLOTS.find(s => s.id === activeSlot)!
  const currentSlotData = dayData?.[activeSlot] as CheckIn | undefined
  const isFilled = !!currentSlotData

  // Сброс формы при смене даты или слота
  useEffect(() => {
    setEnergy(3)
    setMood(3)
    setDayResult('')
    setNotes('')
    setBlockers('')
    setWins('')
    setSubmitError(null)
    setShowHint(false)
    setIsEditMode(false)   // сбросить режим редактирования при смене слота/дня
    setSelectedGoalId(null)  // сбросить привязку к цели
    setProgressPct(0)
    setShowGoalSelector(false)
  }, [selectedDate, activeSlot])

  // Пре-заполнение формы данными существующего чекина при входе в режим редактирования
  useEffect(() => {
    if (isEditMode && currentSlotData) {
      setEnergy(currentSlotData.energy_level ?? 3)
      setMood(MOOD_TO_NUM[currentSlotData.mood ?? 'ok'] ?? 3)
      setNotes(currentSlotData.notes ?? '')
      setBlockers(currentSlotData.blockers ?? '')
      setWins(currentSlotData.wins ?? '')
    }
  }, [isEditMode])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = () => {
    setSubmitError(null)

    const dto: CreateCheckInDto = {
      time_slot: activeSlot,
      check_date: selectedDate,
    }

    if (activeSlot === 'morning') {
      dto.energy_level = energy
      if (notes.trim()) dto.notes = notes.trim()  // заметки утром тоже сохраняем
    } else if (activeSlot === 'midday') {
      dto.energy_level = energy
      if (notes.trim()) dto.notes = notes.trim()
    } else {
      // evening: настроение + итог дня + победы + блокеры
      dto.mood = NUM_TO_MOOD[mood] ?? 'ok'  // конвертируем 1-5 → 'bad'|'tired'|'ok'|'good'|'great'
      const noteParts = [
        dayResult ? DAY_RESULTS.find(r => r.key === dayResult)?.label ?? '' : '',
        notes.trim(),
      ].filter(Boolean)
      if (noteParts.length > 0) dto.notes = noteParts.join('\n')
      if (blockers.trim()) dto.blockers = blockers.trim()
      if (wins.trim()) dto.wins = wins.trim()
    }

    if (isEditMode && currentSlotData) {
      // PATCH — обновление существующего чекина
      updateCheckIn.mutate(
        { id: currentSlotData.id, ...dto },
        {
          onSuccess: () => setIsEditMode(false),
          onError: () => setSubmitError('Не удалось обновить. Попробуй ещё раз.'),
        },
      )
    } else {
      // POST — создание нового чекина (остаёмся на странице, запросы инвалидируются в хуке)
      createCheckIn.mutate(dto, {
        onSuccess: () => {},
        onError: () => setSubmitError('Не удалось сохранить. Попробуй ещё раз.'),
      })
    }
  }

  const isToday = selectedDate === today
  const dateLabel = isToday
    ? 'Сегодня'
    : new Date(selectedDate + 'T00:00:00').toLocaleDateString('ru', {
        day: 'numeric', month: 'long',
      })

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* Шапка */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/coaching')}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-black" style={{ color: 'var(--app-text)' }}>
            Чекин дня
          </h1>
          <p className="text-xs font-medium" style={{ color: slotInfo.color }}>
            {dateLabel} · {slotInfo.label}
          </p>
        </div>
        {/* Кнопка инструкции */}
        <button
          onClick={() => navigate('/coaching/checkin/help')}
          className="flex items-center gap-1.5 px-3 h-9 rounded-xl shrink-0"
          style={{ background: 'rgba(255,255,255,0.06)' }}
          title="Инструкция по чекинам"
        >
          <HelpCircle size={15} style={{ color: '#64748b' }} />
          <span className="text-xs font-medium" style={{ color: '#64748b' }}>Справка</span>
        </button>
      </div>

      {/* DayStrip: 15 дней с точками */}
      <div className="px-4 pb-3 shrink-0">
        <DayStrip
          days={days}
          selectedDate={selectedDate}
          onSelect={setSelectedDate}
          calendarData={calendarData}
        />
      </div>

      {/* SlotTabs: Утро / День / Вечер */}
      <div className="px-4 pb-3 shrink-0">
        <div
          className="flex rounded-2xl p-1"
          style={{ background: 'rgba(255,255,255,0.05)' }}
        >
          {SLOTS.map(slot => {
            const isActive = activeSlot === slot.id
            const filled = (calendarData[selectedDate] ?? []).includes(slot.id)
            return (
              <motion.button
                key={slot.id}
                whileTap={{ scale: 0.95 }}
                onClick={() => setActiveSlot(slot.id)}
                className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-semibold transition-all"
                style={
                  isActive
                    ? {
                        background: `${slot.color}22`,
                        color: slot.color,
                        border: `1px solid ${slot.color}40`,
                      }
                    : {
                        color: filled ? slot.color : 'var(--app-hint)',
                        border: '1px solid transparent',
                        opacity: filled ? 0.75 : 1,
                      }
                }
              >
                <span
                  style={{
                    color: isActive ? slot.color : 'var(--app-hint)',
                    opacity: isActive ? 1 : 0.5,
                  }}
                >
                  {SLOT_ICONS[slot.id]}
                </span>
                {slot.label}
                {filled && !isActive && (
                  <div
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ background: slot.color }}
                  />
                )}
              </motion.button>
            )
          })}
        </div>
      </div>

      {/* Скролл-область */}
      <div className="flex-1 overflow-y-auto px-4 pb-28 space-y-3">

        {/* DaySummaryCard — показываем, когда ≥2 слота заполнены */}
        {Object.values(dayData ?? {}).filter(Boolean).length >= 2 && (
          <DaySummaryCard dayData={(dayData ?? {}) as Record<string, CheckIn | undefined>} />
        )}

        {/* Подсказка — когда и зачем */}
        <button
          onClick={() => setShowHint(v => !v)}
          className="w-full text-left px-3 py-2 rounded-xl flex items-start gap-2"
          style={{
            background: 'rgba(99,102,241,0.07)',
            border: '1px solid rgba(99,102,241,0.15)',
          }}
        >
          <span className="text-sm mt-0.5 shrink-0">ℹ️</span>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium" style={{ color: '#a5b4fc' }}>
              {slotInfo.label} — когда и зачем?
            </p>
            <AnimatePresence>
              {showHint && (
                <motion.p
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="text-xs mt-1 leading-relaxed overflow-hidden"
                  style={{ color: '#c4b5fd' }}
                >
                  {slotInfo.hint}
                </motion.p>
              )}
            </AnimatePresence>
          </div>
          <ChevronDown
            size={14}
            style={{
              color: '#818cf8',
              transform: showHint ? 'rotate(180deg)' : 'rotate(0)',
              transition: 'transform 0.2s',
              flexShrink: 0,
            }}
          />
        </button>

        {/* Лоадер */}
        {isLoading ? (
          <div className="flex justify-center py-10">
            <div
              className="w-6 h-6 rounded-full border-2 border-t-transparent animate-spin"
              style={{ borderColor: `${slotInfo.color} transparent ${slotInfo.color} transparent` }}
            />
          </div>

        ) : isFilled && !isEditMode ? (
          /* Read-only вид */
          <AnimatePresence mode="wait">
            <motion.div
              key={activeSlot + selectedDate + '-ro'}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              <SlotReadonly checkin={currentSlotData!} slot={activeSlot} onEdit={() => setIsEditMode(true)} />
            </motion.div>
          </AnimatePresence>

        ) : (
          /* Форма (новая или редактирование) */
          <AnimatePresence mode="wait">
            <motion.div
              key={activeSlot + selectedDate + '-form'}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >

              {/* УТРО: энергия + главный фокус дня */}
              {activeSlot === 'morning' && (
                <>
                  <GlassCard>
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-semibold" style={{ color: 'var(--app-text)' }}>
                        ⚡ Уровень энергии
                      </p>
                      <span
                        className="text-xs font-medium px-2 py-0.5 rounded-lg"
                        style={{ background: 'rgba(251,191,36,0.15)', color: '#fbbf24' }}
                      >
                        {ENERGY_TEXT[energy - 1]}
                      </span>
                    </div>
                    <p className="text-xs mb-3" style={{ color: 'var(--app-hint)' }}>
                      1 — истощён, 5 — горю 🔥
                    </p>
                    <ScaleSelector
                      value={energy}
                      onChange={setEnergy}
                      emojis={ENERGY_EMOJI}
                      texts={ENERGY_TEXT}
                      color="#fbbf24"
                    />
                  </GlassCard>
                  {/* Главный фокус дня (§13.1) — сохраняется в notes */}
                  <GlassCard>
                    <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>
                      🎯 Главный фокус сегодня
                    </p>
                    <textarea
                      placeholder="Что самое важное сделать сегодня? (необязательно)"
                      value={notes}
                      onChange={e => setNotes(e.target.value)}
                      rows={2}
                      className="w-full text-sm outline-none resize-none bg-transparent"
                      style={{ color: 'var(--app-text)', caretColor: '#fbbf24' }}
                    />
                  </GlassCard>
                </>
              )}

              {/* ДЕНЬ: энергия + короткая заметка */}
              {activeSlot === 'midday' && (
                <>
                  <GlassCard>
                    <div className="flex items-center justify-between mb-1">
                      <p className="font-semibold" style={{ color: 'var(--app-text)' }}>
                        ⚡ Энергия сейчас
                      </p>
                      <span
                        className="text-xs font-medium px-2 py-0.5 rounded-lg"
                        style={{ background: 'rgba(34,211,238,0.15)', color: '#22d3ee' }}
                      >
                        {ENERGY_TEXT[energy - 1]}
                      </span>
                    </div>
                    <p className="text-xs mb-3" style={{ color: 'var(--app-hint)' }}>
                      1 — еле живой, 5 — на подъёме
                    </p>
                    <ScaleSelector
                      value={energy}
                      onChange={setEnergy}
                      emojis={ENERGY_EMOJI}
                      texts={ENERGY_TEXT}
                      color="#22d3ee"
                    />
                  </GlassCard>
                  <GlassCard>
                    <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>
                      💬 Коротко о дне
                    </p>
                    <textarea
                      placeholder="Как идут дела? Что в фокусе? (необязательно)"
                      value={notes}
                      onChange={e => setNotes(e.target.value)}
                      rows={2}
                      className="w-full text-sm outline-none resize-none bg-transparent"
                      style={{ color: 'var(--app-text)', caretColor: '#22d3ee' }}
                    />
                  </GlassCard>
                </>
              )}

              {/* ВЕЧЕР: настроение + итог + победы + блокеры */}
              {activeSlot === 'evening' && (
                <>
                  {/* 5 быстрых кнопок настроения (§9.3) */}
                  <GlassCard>
                    <div className="flex items-center justify-between mb-3">
                      <p className="font-semibold" style={{ color: 'var(--app-text)' }}>
                        😊 Как прошёл вечер?
                      </p>
                      {mood > 0 && (
                        <span
                          className="text-xs font-medium px-2 py-0.5 rounded-lg"
                          style={{ background: `${MOOD_QUICK.find(m => m.value === mood)?.color ?? '#a78bfa'}25`, color: MOOD_QUICK.find(m => m.value === mood)?.color ?? '#a78bfa' }}
                        >
                          {MOOD_QUICK.find(m => m.value === mood)?.label}
                        </span>
                      )}
                    </div>
                    <div className="grid grid-cols-5 gap-1.5">
                      {MOOD_QUICK.map(m => (
                        <motion.button
                          key={m.value}
                          whileTap={{ scale: 0.88 }}
                          onClick={() => setMood(m.value)}
                          className="flex flex-col items-center gap-1 py-2.5 rounded-xl"
                          style={
                            mood === m.value
                              ? { background: `${m.color}25`, border: `1.5px solid ${m.color}60` }
                              : { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }
                          }
                        >
                          <span className="text-xl">{m.emoji}</span>
                          <span className="text-[10px] leading-tight text-center" style={{ color: mood === m.value ? m.color : 'var(--app-hint)' }}>{m.label}</span>
                        </motion.button>
                      ))}
                    </div>
                  </GlassCard>

                  <GlassCard>
                    <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>
                      📊 Как прошёл день?
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      {DAY_RESULTS.map(r => (
                        <motion.button
                          key={r.key}
                          whileTap={{ scale: 0.94 }}
                          onClick={() =>
                            setDayResult(prev => (prev === r.key ? '' : r.key))
                          }
                          className="py-2.5 px-3 rounded-xl text-xs font-medium text-left"
                          style={{
                            background:
                              dayResult === r.key
                                ? 'rgba(167,139,250,0.2)'
                                : 'rgba(255,255,255,0.05)',
                            border: `1px solid ${
                              dayResult === r.key
                                ? 'rgba(167,139,250,0.4)'
                                : 'rgba(255,255,255,0.07)'
                            }`,
                            color:
                              dayResult === r.key ? '#c4b5fd' : 'var(--app-hint)',
                          }}
                        >
                          {r.label}
                        </motion.button>
                      ))}
                    </div>
                    <textarea
                      placeholder="Что-то важное о дне? (необязательно)"
                      value={notes}
                      onChange={e => setNotes(e.target.value)}
                      rows={2}
                      className="w-full text-sm outline-none resize-none bg-transparent mt-3 pt-3"
                      style={{
                        color: 'var(--app-text)',
                        caretColor: '#a78bfa',
                        borderTop: '1px solid rgba(255,255,255,0.06)',
                      }}
                    />
                  </GlassCard>

                  <GlassCard>
                    <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>
                      🏆 Победы дня
                    </p>
                    <textarea
                      placeholder="Что удалось, пусть даже маленькое..."
                      value={wins}
                      onChange={e => setWins(e.target.value)}
                      rows={2}
                      className="w-full text-sm outline-none resize-none bg-transparent"
                      style={{ color: 'var(--app-text)', caretColor: '#a78bfa' }}
                    />
                  </GlassCard>

                  <GlassCard>
                    <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>
                      🚧 Что мешало?
                    </p>
                    <textarea
                      placeholder="Блокеры, трудности, отвлечения... (необязательно)"
                      value={blockers}
                      onChange={e => setBlockers(e.target.value)}
                      rows={2}
                      className="w-full text-sm outline-none resize-none bg-transparent"
                      style={{ color: 'var(--app-text)', caretColor: '#a78bfa' }}
                    />
                  </GlassCard>

                  {/* Привязка к цели + прогресс (опционально) */}
                  {activeGoals.length > 0 && (
                    <GlassCard>
                      <button
                        onClick={() => setShowGoalSelector(v => !v)}
                        className="w-full flex items-center justify-between"
                      >
                        <span className="text-sm font-semibold" style={{ color: selectedGoalId ? '#c4b5fd' : 'var(--app-hint)' }}>
                          🎯 {selectedGoalId
                            ? (activeGoals.find(g => g.id === selectedGoalId)?.title ?? 'Цель выбрана')
                            : 'Привязать к цели'}
                        </span>
                        <ChevronDown
                          size={14}
                          style={{ color: '#818cf8', transform: showGoalSelector ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s', flexShrink: 0 }}
                        />
                      </button>
                      <AnimatePresence>
                        {showGoalSelector && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: 'auto' }}
                            exit={{ opacity: 0, height: 0 }}
                            className="mt-3 space-y-2 overflow-hidden"
                          >
                            {/* Сброс выбора */}
                            {selectedGoalId && (
                              <motion.button
                                whileTap={{ scale: 0.96 }}
                                onClick={() => { setSelectedGoalId(null); setProgressPct(0) }}
                                className="w-full text-left px-3 py-2 rounded-xl text-xs"
                                style={{ background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)', color: '#f87171' }}
                              >
                                ✕ Убрать привязку
                              </motion.button>
                            )}
                            {activeGoals.map(g => (
                              <motion.button
                                key={g.id}
                                whileTap={{ scale: 0.96 }}
                                onClick={() => setSelectedGoalId(prev => prev === g.id ? null : g.id)}
                                className="w-full text-left px-3 py-2 rounded-xl text-sm"
                                style={{
                                  background: selectedGoalId === g.id ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)',
                                  border: `1px solid ${selectedGoalId === g.id ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.07)'}`,
                                  color: selectedGoalId === g.id ? '#c4b5fd' : 'var(--app-hint)',
                                }}
                              >
                                {g.title} — {g.progress_pct}%
                              </motion.button>
                            ))}
                            {/* Слайдер прогресса */}
                            {selectedGoalId && (
                              <div className="mt-2 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                                <p className="text-xs mb-2" style={{ color: 'var(--app-hint)' }}>
                                  Прогресс по цели: <span style={{ color: '#818cf8', fontWeight: 600 }}>{progressPct}%</span>
                                </p>
                                <input
                                  type="range" min={0} max={100} step={5}
                                  value={progressPct}
                                  onChange={e => setProgressPct(Number(e.target.value))}
                                  className="w-full"
                                  style={{ accentColor: '#818cf8' }}
                                />
                              </div>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </GlassCard>
                  )}
                </>
              )}

            </motion.div>
          </AnimatePresence>
        )}
      </div>

      {/* Кнопка отправки — только в режиме формы */}
      {(!isFilled || isEditMode) && !isLoading && (
        <div
          className="fixed bottom-0 inset-x-0 px-4 py-3"
          style={{
            background: 'var(--app-bg)',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            zIndex: 55,  // выше BottomNav (z-index: 50) чтобы кнопка была кликабельна
            paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom, 0px))',
          }}
        >
          {submitError && (
            <p className="text-xs text-center mb-2" style={{ color: '#f87171' }}>
              {submitError}
            </p>
          )}
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={handleSubmit}
            disabled={createCheckIn.isPending || updateCheckIn.isPending}
            className="w-full rounded-2xl py-4 font-bold flex items-center justify-center gap-2 disabled:opacity-40"
            style={{
              background: `linear-gradient(135deg, ${slotInfo.color}dd, ${slotInfo.color}88)`,
              color: activeSlot === 'morning' ? '#1c1c1e' : '#fff',
            }}
          >
            {SLOT_ICONS[activeSlot]}
            {(createCheckIn.isPending || updateCheckIn.isPending)
              ? 'Сохраняем...'
              : isEditMode
              ? 'Сохранить изменения'
              : `Сохранить — ${slotInfo.label}`}
          </motion.button>
        </div>
      )}
    </div>
  )
}
