/**
 * CheckInPage v2 — экран чекина дня.
 *
 * Изменения согласно docs/coaching-architecture.md:
 *  §13.5 — прогресс-индикатор, quick/extended режимы, привязка к цели
 *  §9.3  — чипы быстрого ответа после выбора настроения
 *  §8.1  — адаптивный вопрос коуча на основе выбранного настроения
 *  §11.3 — примеры-чипы в текстовых полях для подсказки
 *  §13.9 — голосовой ввод (SpeechRecognition API), chat bridge
 */
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Send, Mic, MicOff,
  ChevronDown, ChevronUp, Target, MessageCircle,
} from 'lucide-react'
import { useCreateCheckIn, useGoals } from '../../api/coaching'
import type { CreateCheckInDto } from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'

// ── Конфигурация шкал ─────────────────────────────────────────────────────────
const ENERGY_EMOJI = ['😴', '😔', '😐', '🙂', '🔥']
const ENERGY_TEXT  = ['Истощён', 'Устал', 'Нейтрально', 'Бодро', 'Горю!']

const MOOD_EMOJI = ['😢', '😕', '😐', '🙂', '😄']
const MOOD_TEXT  = ['Плохо', 'Грустно', 'Нейтрально', 'Хорошо', 'Отлично!']

// Маппинг числового значения настроения в строковый enum API
const MOOD_MAP: Record<number, string> = {
  1: 'bad', 2: 'tired', 3: 'ok', 4: 'good', 5: 'great',
}

// ── Адаптивный вопрос коуча после выбора настроения (§8.1) ────────────────────
function coachQuestion(mood: number): string {
  if (mood <= 2) return 'Что случилось? Иногда просто написать об этом — уже шаг вперёд.'
  if (mood === 3) return 'Ничего особенного? Что хотя бы немного порадовало сегодня?'
  return 'Отлично! Что именно сделало этот день хорошим?'
}

// ── Адаптивный placeholder для рефлексии в зависимости от настроения ─────────
function reflectionHint(mood: number): string {
  if (mood <= 2) return 'Расскажи, что было тяжело. Писать об этом — тоже шаг вперёд...'
  if (mood >= 4) return 'Что сделало этот день хорошим? Чем гордишься?'
  return 'Как прошёл день? Что было важным?'
}

// ── Чипы-примеры для текстовых полей (§11.3) ─────────────────────────────────
const REFLECTION_CHIPS = [
  'Продуктивный день 💪',
  'Всё шло по плану',
  'Были трудности, но справился',
  'Тяжёлый день',
]
const BLOCKERS_CHIPS = [
  'Отвлекался на несрочное',
  'Не хватило времени',
  'Усталость',
  'Внешние помехи',
]
const WINS_CHIPS = [
  'Завершил важную задачу',
  'Держал все привычки',
  'Сделал сложный шаг',
  'Помог кому-то',
]

// ── Чипы быстрого действия после выбора настроения (§9.3) ────────────────────
type QuickAction = 'expand_blockers' | 'expand_wins' | 'submit'
interface QuickChip { label: string; action: QuickAction }

function getMoodChips(mood: number): QuickChip[] {
  if (mood <= 2) return [
    { label: '😔 Расскажу что мешало', action: 'expand_blockers' },
    { label: '💡 Дай следующий шаг',   action: 'submit' },
  ]
  if (mood >= 4) return [
    { label: '🏆 Записать победы',   action: 'expand_wins' },
    { label: '✅ Всё ок, сохранить', action: 'submit' },
  ]
  return [
    { label: '📝 Расскажу подробнее', action: 'expand_blockers' },
    { label: '✅ Всё в порядке',      action: 'submit' },
  ]
}

// ── ScaleSelector: шкала 1-5 с эмодзи и текстовым лейблом ───────────────────
interface ScaleSelectorProps {
  value: number
  onChange: (v: number) => void
  emojis: string[]
  texts: string[]
  accentColor?: string
}

function ScaleSelector({
  value, onChange, emojis, texts, accentColor = 'rgba(99,102,241,0.35)',
}: ScaleSelectorProps) {
  return (
    <div>
      <div className="flex gap-2 justify-between">
        {[1, 2, 3, 4, 5].map(n => (
          <motion.button
            key={n}
            whileTap={{ scale: 0.85 }}
            onClick={() => onChange(n)}
            className="flex-1 aspect-square rounded-xl text-2xl flex items-center justify-center transition-all"
            style={
              value === n
                ? { background: accentColor, border: '1px solid rgba(99,102,241,0.5)' }
                : { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.06)' }
            }
          >
            {emojis[n - 1]}
          </motion.button>
        ))}
      </div>
      {/* Текстовый лейбл выбранного значения */}
      <p
        className="text-center text-xs mt-2 font-medium transition-all"
        style={{ color: '#a5b4fc' }}
      >
        {texts[value - 1]}
      </p>
    </div>
  )
}

// ── ExampleChips: горизонтальные чипы-примеры для textarea ───────────────────
function ExampleChips({
  chips, onSelect,
}: { chips: string[]; onSelect: (chip: string) => void }) {
  return (
    <div className="flex gap-2 flex-wrap mt-2">
      {chips.map(chip => (
        <motion.button
          key={chip}
          whileTap={{ scale: 0.95 }}
          onClick={() => onSelect(chip)}
          className="px-2.5 py-1 rounded-xl text-xs border border-white/[0.08] whitespace-nowrap"
          style={{ background: 'rgba(99,102,241,0.08)', color: '#a5b4fc' }}
        >
          {chip}
        </motion.button>
      ))}
    </div>
  )
}

// ── VoiceMicButton: кнопка голосового ввода (SpeechRecognition) ───────────────
// Использует Web Speech API.
// Паттерн useRef для onAppend — исключает stale closure при повторных рендерах.
function VoiceMicButton({ onAppend }: { onAppend: (text: string) => void }) {
  const [listening, setListening] = useState(false)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recRef = useRef<any>(null)
  // Всегда актуальная ссылка на коллбэк — обновляется синхронно при каждом рендере
  const onAppendRef = useRef(onAppend)
  onAppendRef.current = onAppend

  // Проверяем поддержку SpeechRecognition в браузере
  const isSupported =
    typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)

  function handleToggle() {
    if (listening) {
      // abort не ждёт результата — сразу останавливает
      recRef.current?.abort?.()
      recRef.current?.stop?.()
      setListening(false)
      return
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    const rec = new SR()
    rec.lang = 'ru-RU'
    rec.continuous = false
    rec.interimResults = false
    rec.maxAlternatives = 1
    // Используем onAppendRef.current — всегда свежий коллбэк без stale closure
    rec.onresult = (e: any) => {  // eslint-disable-line @typescript-eslint/no-explicit-any
      let transcript = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        transcript += e.results[i][0].transcript
      }
      if (transcript.trim()) onAppendRef.current(transcript.trim() + ' ')
    }
    rec.onend   = () => setListening(false)
    rec.onerror = (e: any) => {  // eslint-disable-line @typescript-eslint/no-explicit-any
      console.warn('SpeechRecognition error:', e.error)
      setListening(false)
    }
    recRef.current = rec
    try {
      rec.start()
      setListening(true)
    } catch {
      setListening(false)
    }
  }

  if (!isSupported) return null

  return (
    <motion.button
      whileTap={{ scale: 0.85 }}
      onClick={handleToggle}
      className="p-1.5 rounded-lg flex items-center gap-1"
      style={{
        background: listening ? 'rgba(239,68,68,0.2)' : 'rgba(99,102,241,0.1)',
      }}
      title={listening ? 'Остановить запись' : 'Голосовой ввод'}
    >
      {listening
        ? <MicOff size={14} style={{ color: '#f87171' }} />
        : <Mic     size={14} style={{ color: '#818cf8' }} />
      }
      {listening && (
        <span className="text-[10px]" style={{ color: '#f87171' }}>Слушаю...</span>
      )}
    </motion.button>
  )
}

// ── Открыть чат Telegram (закрыть Mini App) ───────────────────────────────────
function openTelegramChat() {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(window as any).Telegram?.WebApp?.close()
}

// Ключ черновика в sessionStorage — форма восстанавливается при возвращении на страницу
const DRAFT_KEY = 'checkin_draft'

export function CheckInPage() {
  const navigate = useNavigate()

  // ── Загружаем черновик из sessionStorage (если пользователь вернулся назад) ──
  const savedDraft = (() => {
    try { return JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? 'null') } catch { return null }
  })()

  // ── Состояние формы — восстанавливается из черновика, иначе дефолты ─────────
  const [extended, setExtended]         = useState<boolean>(savedDraft?.extended   ?? true)
  const [energy, setEnergy]             = useState<number>(savedDraft?.energy      ?? 3)
  const [mood, setMood]                 = useState<number>(savedDraft?.mood        ?? 3)
  const [reflection, setReflection]     = useState<string>(savedDraft?.reflection  ?? '')
  const [blockers, setBlockers]         = useState<string>(savedDraft?.blockers    ?? '')
  const [wins, setWins]                 = useState<string>(savedDraft?.wins        ?? '')
  const [goalId, setGoalId]             = useState<number | undefined>(savedDraft?.goalId)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Ref для прокрутки к полю блокеров при чипе «Расскажу что мешало»
  const blockersRef = useRef<HTMLDivElement>(null)
  const winsRef     = useRef<HTMLDivElement>(null)

  const createCheckIn = useCreateCheckIn()
  // Загружаем активные цели для выбора привязки (§13.5)
  const { data: activeGoals = [] } = useGoals('active')

  // ── Сохраняем черновик при каждом изменении полей ─────────────────────────
  useEffect(() => {
    try {
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify({
        extended, energy, mood, reflection, blockers, wins, goalId,
      }))
    } catch { /* sessionStorage недоступен */ }
  }, [extended, energy, mood, reflection, blockers, wins, goalId])

  // ── Прогресс-индикатор ──────────────────────────────────────────────────────
  // Считаем заполненные поля: energy + mood всегда заполнены (есть дефолт),
  // текстовые поля — когда написано > 3 символов
  const textFilled    = [reflection, ...(extended ? [blockers, wins] : [])].filter(s => s.trim().length > 3).length
  const totalFields   = extended ? 5 : 3    // energy + mood + текстовые
  const filledFields  = 2 + textFilled       // energy и mood всегда 2
  const progressPct   = Math.round((filledFields / totalFields) * 100)

  // Цвет прогресс-бара по заполненности
  const progressColor =
    progressPct >= 80 ? '#4ade80' :
    progressPct >= 50 ? '#818cf8' : '#fbbf24'

  // ── Обработка смены настроения ───────────────────────────────────────────────
  const handleMoodChange = (v: number) => {
    setMood(v)
  }

  // ── Обработка быстрых чипов после настроения (§9.3) ─────────────────────────
  const handleQuickChip = (action: QuickAction) => {
    if (action === 'expand_blockers') {
      setExtended(true)
      // Прокручиваем к полю блокеров через небольшую задержку
      setTimeout(() => blockersRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150)
    } else if (action === 'expand_wins') {
      setExtended(true)
      setTimeout(() => winsRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 150)
    } else if (action === 'submit') {
      handleSubmit()
    }
  }

  // ── Отправка чекина ──────────────────────────────────────────────────────────
  const handleSubmit = () => {
    setSubmitError(null)
    const dto: CreateCheckInDto = {
      energy_level: energy,
      mood:         MOOD_MAP[mood],
      notes:        reflection.trim()  || undefined,
      blockers:     blockers.trim()    || undefined,
      wins:         wins.trim()        || undefined,
      goal_id:      goalId,
    }
    createCheckIn.mutate(dto, {
      onSuccess: () => {
        // Очищаем черновик при успешной отправке
        try { sessionStorage.removeItem(DRAFT_KEY) } catch {}
        navigate('/coaching')
      },
      onError:   () => setSubmitError('Не удалось сохранить чекин. Попробуй ещё раз.'),
    })
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">

      {/* ── Шапка ─────────────────────────────────────────────────────────── */}
      <div className="px-4 pt-6 pb-2 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/coaching')}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-xl font-black flex-1" style={{ color: 'var(--app-text)' }}>
          Чекин дня
        </h1>
        {/* Кнопка чата (§13.9 — chat bridge) */}
        <button
          onClick={openTelegramChat}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)' }}
          title="Открыть в чате"
        >
          <MessageCircle size={18} style={{ color: '#818cf8' }} />
        </button>
        {/* Переключатель режима */}
        <button
          onClick={() => setExtended(v => !v)}
          className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-xl border border-white/[0.08]"
          style={{ background: 'rgba(255,255,255,0.05)', color: '#818cf8' }}
        >
          {extended
            ? <><ChevronUp size={14} /> Кратко</>
            : <><ChevronDown size={14} /> Подробно</>
          }
        </button>
      </div>

      {/* ── Прогресс-индикатор (§13.5) ────────────────────────────────────── */}
      <div className="px-4 pb-3 shrink-0">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px]" style={{ color: 'var(--app-hint)' }}>
            Заполнено
          </span>
          <span
            className="text-[11px] font-semibold"
            style={{ color: progressColor }}
          >
            {filledFields}/{totalFields}
          </span>
        </div>
        <div
          className="h-1 rounded-full overflow-hidden"
          style={{ background: 'rgba(255,255,255,0.08)' }}
        >
          <motion.div
            className="h-full rounded-full"
            initial={{ width: 0 }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.4 }}
            style={{ background: progressColor }}
          />
        </div>
      </div>

      {/* ── Скролл-область ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 pb-28 space-y-4">

        {/* ── Энергия ─────────────────────────────────────────────────────── */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold" style={{ color: 'var(--app-text)' }}>⚡ Энергия</p>
            <span className="text-xs font-medium px-2 py-0.5 rounded-lg"
              style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}>
              {ENERGY_TEXT[energy - 1]}
            </span>
          </div>
          <ScaleSelector
            value={energy}
            onChange={setEnergy}
            emojis={ENERGY_EMOJI}
            texts={ENERGY_TEXT}
          />
        </GlassCard>

        {/* ── Настроение ──────────────────────────────────────────────────── */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold" style={{ color: 'var(--app-text)' }}>😊 Настроение</p>
            <span className="text-xs font-medium px-2 py-0.5 rounded-lg"
              style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}>
              {MOOD_TEXT[mood - 1]}
            </span>
          </div>
          <ScaleSelector
            value={mood}
            onChange={handleMoodChange}
            emojis={MOOD_EMOJI}
            texts={MOOD_TEXT}
          />

          {/* Адаптивный вопрос коуча (§8.1) — появляется после первого выбора настроения */}
          <AnimatePresence mode="wait">
              <motion.div
                key={"coach-q-" + mood}
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mt-3 px-3 py-2 rounded-xl text-xs leading-relaxed"
                style={{ background: 'rgba(99,102,241,0.1)', color: '#c4b5fd' }}
              >
                💬 {coachQuestion(mood)}
              </motion.div>
          </AnimatePresence>

          {/* Чипы быстрого действия (§9.3) */}
          <AnimatePresence mode="wait">
              <motion.div
                key={"mood-chips-" + mood}
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex gap-2 mt-3 flex-wrap"
              >
                {getMoodChips(mood).map(chip => (
                  <motion.button
                    key={chip.label}
                    whileTap={{ scale: 0.93 }}
                    onClick={() => handleQuickChip(chip.action)}
                    className="px-3 py-1.5 rounded-xl text-xs font-medium border border-white/[0.08]"
                    style={{ background: 'rgba(139,92,246,0.12)', color: '#c4b5fd' }}
                  >
                    {chip.label}
                  </motion.button>
                ))}
              </motion.div>
          </AnimatePresence>
        </GlassCard>

        {/* ── Рефлексия — «Как прошёл день?» ─────────────────────────────── */}
        <GlassCard>
          <div className="flex items-center justify-between mb-2">
            <p className="font-semibold" style={{ color: 'var(--app-text)' }}>
              💬 Как прошёл день?
            </p>
            {/* Голосовой ввод (§13.9) */}
            <VoiceMicButton onAppend={text => setReflection(prev => prev + text)} />
          </div>
          <textarea
            placeholder={reflectionHint(mood)}
            value={reflection}
            onChange={e => setReflection(e.target.value)}
            rows={3}
            className="w-full text-sm outline-none resize-none bg-transparent"
            style={{ color: 'var(--app-text)', caretColor: '#818cf8' }}
          />
          {/* Примеры-чипы для заполнения поля (§11.3) */}
          <ExampleChips
            chips={REFLECTION_CHIPS}
            onSelect={chip => setReflection(prev => prev ? `${prev} ${chip}` : chip)}
          />
        </GlassCard>

        {/* ── Расширенный режим (§13.5) ────────────────────────────────────── */}
        <AnimatePresence>
          {extended && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="space-y-4"
            >
              {/* Блокеры */}
              <div ref={blockersRef}>
                <GlassCard>
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-semibold" style={{ color: 'var(--app-text)' }}>
                      🚧 Что мешало?
                    </p>
                    <VoiceMicButton onAppend={text => setBlockers(prev => prev + text)} />
                  </div>
                  <textarea
                    placeholder="Расскажи, что блокировало прогресс..."
                    value={blockers}
                    onChange={e => setBlockers(e.target.value)}
                    rows={2}
                    className="w-full text-sm outline-none resize-none bg-transparent"
                    style={{ color: 'var(--app-text)', caretColor: '#818cf8' }}
                  />
                  <ExampleChips
                    chips={BLOCKERS_CHIPS}
                    onSelect={chip => setBlockers(prev => prev ? `${prev}, ${chip}` : chip)}
                  />
                </GlassCard>
              </div>

              {/* Победы */}
              <div ref={winsRef}>
                <GlassCard>
                  <div className="flex items-center justify-between mb-2">
                    <p className="font-semibold" style={{ color: 'var(--app-text)' }}>
                      🏆 Победы дня
                    </p>
                    <VoiceMicButton onAppend={text => setWins(prev => prev + text)} />
                  </div>
                  <textarea
                    placeholder="Чем гордишься сегодня?"
                    value={wins}
                    onChange={e => setWins(e.target.value)}
                    rows={2}
                    className="w-full text-sm outline-none resize-none bg-transparent"
                    style={{ color: 'var(--app-text)', caretColor: '#818cf8' }}
                  />
                  <ExampleChips
                    chips={WINS_CHIPS}
                    onSelect={chip => setWins(prev => prev ? `${prev}, ${chip}` : chip)}
                  />
                </GlassCard>
              </div>

              {/* Привязка к цели (§13.5) */}
              {activeGoals.length > 0 && (
                <GlassCard>
                  <div className="flex items-center gap-2 mb-3">
                    <Target size={16} style={{ color: '#818cf8' }} />
                    <p className="font-semibold text-sm" style={{ color: 'var(--app-text)' }}>
                      Привязать к цели
                    </p>
                    {goalId && (
                      <button
                        onClick={() => setGoalId(undefined)}
                        className="ml-auto text-xs"
                        style={{ color: 'var(--app-hint)' }}
                      >
                        Снять
                      </button>
                    )}
                  </div>
                  {/* Горизонтальный скролл-список активных целей */}
                  <div
                    className="flex gap-2 overflow-x-auto pb-1"
                    style={{ scrollbarWidth: 'none' }}
                  >
                    {activeGoals.slice(0, 6).map(g => (
                      <motion.button
                        key={g.id}
                        whileTap={{ scale: 0.93 }}
                        onClick={() => setGoalId(g.id === goalId ? undefined : g.id)}
                        className="flex-shrink-0 px-3 py-2 rounded-xl text-xs font-medium border border-white/[0.08] text-left"
                        style={{
                          maxWidth: 140,
                          background: goalId === g.id
                            ? 'rgba(99,102,241,0.25)'
                            : 'rgba(255,255,255,0.05)',
                          color: goalId === g.id ? '#c4b5fd' : 'var(--app-hint)',
                          borderColor: goalId === g.id ? 'rgba(99,102,241,0.5)' : 'rgba(255,255,255,0.06)',
                          overflow: 'hidden',
                          whiteSpace: 'nowrap',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {g.id === goalId ? '✓ ' : ''}{g.title}
                      </motion.button>
                    ))}
                  </div>
                </GlassCard>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Sticky кнопка отправки ────────────────────────────────────────── */}
      <div
        className="fixed bottom-0 inset-x-0 px-4 py-3"
        style={{ background: 'var(--app-bg)', borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        {submitError && (
          <p className="text-xs text-center mb-2" style={{ color: '#f87171' }}>
            {submitError}
          </p>
        )}
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleSubmit}
          disabled={createCheckIn.isPending}
          className="w-full rounded-2xl py-4 font-bold flex items-center justify-center gap-2 disabled:opacity-40"
          style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
        >
          <Send size={18} />
          {createCheckIn.isPending ? 'Сохраняем...' : 'Сохранить чекин'}
        </motion.button>
      </div>
    </div>
  )
}
