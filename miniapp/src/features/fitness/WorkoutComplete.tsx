/**
 * Экран завершения тренировки.
 * Показывает статистику: длительность, объём, количество упражнений/подходов,
 * личные рекорды с анимацией, выбор настроения (1-5).
 */
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Trophy, Timer, Dumbbell, Flame, TrendingUp, ArrowRight, Apple, FileText, Save } from 'lucide-react'
import { useFinishSession, usePostWorkoutTips, useCreateTemplate, type WorkoutSession } from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'

/** Данные, переданные через navigate state из ActiveWorkout */
/** Данные упражнения для создания шаблона */
interface TemplateExerciseData {
  exercise_id: number
  exercise_name: string
  exercise_category: string
  sets: number
  reps: number | null
  weight_kg: number | null
  duration_sec: number | null
  rest_sec: number
}

interface CompleteState {
  session: WorkoutSession
  elapsed: number
  exerciseCount: number
  totalSets: number
  totalVolume: number
  exercises?: TemplateExerciseData[]
}

/** Варианты настроения */
const MOODS = [
  { value: 1, emoji: '😫', label: 'Тяжело' },
  { value: 2, emoji: '😕', label: 'Средне' },
  { value: 3, emoji: '😐', label: 'Норм' },
  { value: 4, emoji: '😊', label: 'Хорошо' },
  { value: 5, emoji: '🔥', label: 'Супер!' },
]

export function WorkoutComplete() {
  const navigate = useNavigate()
  const location = useLocation()
  const state = location.state as CompleteState | null
  const finishMut = useFinishSession()

  // Загружаем рекомендации по питанию после тренировки
  const { data: tips } = usePostWorkoutTips(state?.session?.id ?? 0)

  // Выбор настроения
  const [mood, setMood] = useState<number | null>(null)
  const [moodSaved, setMoodSaved] = useState(false)

  // Сохранение как шаблон
  const createTemplateMut = useCreateTemplate()
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [templateName, setTemplateName] = useState('')
  const [templateSaved, setTemplateSaved] = useState(false)

  // Если нет данных — редирект на фитнес
  if (!state?.session) {
    navigate('/fitness', { replace: true })
    return null
  }

  const { session, elapsed, exerciseCount, totalSets, totalVolume } = state

  // Собираем данные упражнений для шаблона: из state.exercises или из session.sets
  const templateExercises = (() => {
    // Если exercises переданы из ActiveWorkout — используем их
    if (state.exercises && state.exercises.length > 0) return state.exercises
    // Fallback: строим список из session.sets (группируем по exercise_id)
    if (!session.sets?.length) return []
    const grouped = new Map<number, { exercise_id: number; sets: number; reps: number; weight_kg: number }>()
    for (const s of session.sets) {
      const existing = grouped.get(s.exercise_id)
      if (existing) {
        existing.sets += 1
        if ((s.weight_kg || 0) > existing.weight_kg) existing.weight_kg = s.weight_kg || 0
        if ((s.reps || 0) > existing.reps) existing.reps = s.reps || 0
      } else {
        grouped.set(s.exercise_id, {
          exercise_id: s.exercise_id,
          sets: 1,
          reps: s.reps || 0,
          weight_kg: s.weight_kg || 0,
        })
      }
    }
    return Array.from(grouped.values()).map((g) => ({
      exercise_id: g.exercise_id,
      exercise_name: `Упражнение #${g.exercise_id}`,
      exercise_category: 'strength',
      sets: g.sets,
      reps: g.reps || null,
      weight_kg: g.weight_kg || null,
      duration_sec: null,
      rest_sec: 60,
    }))
  })()

  // Форматирование времени
  const formatDuration = (sec: number) => {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    if (h > 0) return `${h}ч ${m}м`
    return `${m} мин`
  }

  // Собираем рекорды из подходов сессии
  const records = session.sets?.filter((s) => s.is_personal_record) || []

  // Сохранить настроение
  const handleSaveMood = async () => {
    if (mood === null) return
    try {
      await finishMut.mutateAsync({
        sessionId: session.id,
        dto: { mood_after: mood },
      })
      setMoodSaved(true)
    } catch (e) {
      console.error('Ошибка сохранения настроения:', e)
    }
  }

  // Сохранить тренировку как шаблон
  const handleSaveTemplate = async () => {
    if (!templateName.trim() || !templateExercises.length) return
    try {
      await createTemplateMut.mutateAsync({
        name: templateName.trim(),
        description: `${exerciseCount} упражнений · ${formatDuration(elapsed)}`,
        exercises: templateExercises.map((ex) => ({
          exercise_id: ex.exercise_id,
          sets: ex.sets,
          reps: ex.reps ?? undefined,
          weight_kg: ex.weight_kg ?? undefined,
          duration_sec: ex.duration_sec ?? undefined,
          rest_sec: ex.rest_sec,
        })),
      })
      setTemplateSaved(true)
      setShowTemplateModal(false)
    } catch (e) {
      console.error('Ошибка сохранения шаблона:', e)
    }
  }

  // Анимация появления карточек
  const cardVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: (i: number) => ({
      opacity: 1, y: 0,
      transition: { delay: i * 0.1, duration: 0.4, ease: 'easeOut' as const },
    }),
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="text-center pt-6 pb-4 px-4">
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 200, delay: 0.2 }}
          className="inline-flex items-center justify-center w-20 h-20 rounded-full mb-4 text-4xl"
          style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.2), rgba(16,185,129,0.15))' }}
        >
          🎉
        </motion.div>
        <motion.h1
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="text-xl font-bold"
          style={{ color: 'var(--app-text)' }}
        >
          Тренировка завершена!
        </motion.h1>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.5 }}
          className="text-sm mt-1"
          style={{ color: 'var(--app-hint)' }}
        >
          Отличная работа! Вот твои результаты
        </motion.p>
      </div>

      {/* Контент */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
        {/* ── Основная статистика ── */}
        <motion.div
          custom={0}
          variants={cardVariants}
          initial="hidden"
          animate="visible"
        >
          <GlassCard>
            <div className="grid grid-cols-2 gap-4">
              {/* Длительность */}
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'rgba(99,102,241,0.15)' }}
                >
                  <Timer size={20} style={{ color: '#818cf8' }} />
                </div>
                <div>
                  <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                    {formatDuration(elapsed)}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    длительность
                  </div>
                </div>
              </div>

              {/* Упражнений */}
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'rgba(139,92,246,0.15)' }}
                >
                  <Dumbbell size={20} style={{ color: '#a78bfa' }} />
                </div>
                <div>
                  <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                    {exerciseCount}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    упражнений
                  </div>
                </div>
              </div>

              {/* Подходов */}
              <div className="flex items-center gap-3">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: 'rgba(251,146,60,0.15)' }}
                >
                  <Flame size={20} style={{ color: '#fb923c' }} />
                </div>
                <div>
                  <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                    {totalSets}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    подходов
                  </div>
                </div>
              </div>

              {/* Объём */}
              {totalVolume > 0 && (
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center"
                    style={{ background: 'rgba(34,197,94,0.15)' }}
                  >
                    <TrendingUp size={20} style={{ color: '#22c55e' }} />
                  </div>
                  <div>
                    <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                      {Math.round(totalVolume)} кг
                    </div>
                    <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                      объём
                    </div>
                  </div>
                </div>
              )}
            </div>
          </GlassCard>
        </motion.div>

        {/* ── Личные рекорды ── */}
        {records.length > 0 && (
          <motion.div
            custom={1}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
          >
            <GlassCard>
              <div className="flex items-center gap-2 mb-3">
                <Trophy size={18} style={{ color: '#eab308' }} />
                <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  Новые рекорды! 🏆
                </span>
              </div>
              <div className="space-y-2">
                {records.map((rec, idx) => (
                  <motion.div
                    key={rec.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.6 + idx * 0.15 }}
                    className="flex items-center justify-between p-2 rounded-xl"
                    style={{ background: 'rgba(234,179,8,0.08)' }}
                  >
                    <span className="text-sm" style={{ color: 'var(--app-text)' }}>
                      {rec.exercise_id}
                    </span>
                    <span className="text-sm font-bold" style={{ color: '#eab308' }}>
                      {rec.weight_kg ? `${rec.weight_kg} кг` : `${rec.reps} повт`}
                    </span>
                  </motion.div>
                ))}
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* ── Настроение после тренировки ── */}
        <motion.div
          custom={2}
          variants={cardVariants}
          initial="hidden"
          animate="visible"
        >
          <GlassCard>
            <p className="text-sm font-medium mb-3" style={{ color: 'var(--app-text)' }}>
              Как ощущения?
            </p>
            <div className="flex justify-between mb-3">
              {MOODS.map((m) => (
                <button
                  key={m.value}
                  onClick={() => setMood(m.value)}
                  className="flex flex-col items-center gap-1 p-2 rounded-xl transition-all"
                  style={{
                    background: mood === m.value ? 'rgba(99,102,241,0.2)' : 'transparent',
                    transform: mood === m.value ? 'scale(1.1)' : 'scale(1)',
                    border: mood === m.value ? '1px solid rgba(99,102,241,0.3)' : '1px solid transparent',
                  }}
                >
                  <span className="text-2xl">{m.emoji}</span>
                  <span className="text-[10px]" style={{
                    color: mood === m.value ? '#a5b4fc' : 'var(--app-hint)'
                  }}>
                    {m.label}
                  </span>
                </button>
              ))}
            </div>
            {mood !== null && !moodSaved && (
              <button
                onClick={handleSaveMood}
                disabled={finishMut.isPending}
                className="w-full py-2 rounded-xl text-sm font-medium"
                style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}
              >
                {finishMut.isPending ? 'Сохранение...' : 'Сохранить'}
              </button>
            )}
            {moodSaved && (
              <div className="text-center text-sm" style={{ color: '#22c55e' }}>
                ✓ Сохранено
              </div>
            )}
          </GlassCard>
        </motion.div>

        {/* ── Советы по питанию ── */}
        {tips && tips.tips.length > 0 && (
          <motion.div
            custom={3}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
          >
            <GlassCard>
              <div className="flex items-center gap-2 mb-3">
                <Apple size={18} style={{ color: '#22c55e' }} />
                <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  Питание после тренировки
                </span>
              </div>
              <div className="space-y-2">
                {tips.tips.map((tip, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 text-sm"
                    style={{ color: 'var(--app-text)' }}
                  >
                    <span className="text-xs mt-0.5" style={{ color: '#22c55e' }}>●</span>
                    <span>{tip}</span>
                  </div>
                ))}
              </div>
            </GlassCard>
          </motion.div>
        )}

        {/* ── Сохранить как шаблон ── */}
        {templateExercises.length > 0 && (
          <motion.div
            custom={3.5}
            variants={cardVariants}
            initial="hidden"
            animate="visible"
          >
            <GlassCard>
              {!templateSaved ? (
                <button
                  onClick={() => { setTemplateName(session.name || ''); setShowTemplateModal(true) }}
                  className="w-full flex items-center justify-center gap-2 py-2 text-sm font-medium"
                  style={{ color: '#fb923c' }}
                >
                  <FileText size={18} /> Сохранить как шаблон
                </button>
              ) : (
                <div className="flex items-center justify-center gap-2 py-2 text-sm" style={{ color: '#22c55e' }}>
                  ✓ Шаблон сохранён
                </div>
              )}
            </GlassCard>
          </motion.div>
        )}

        {/* ── Кнопки навигации ── */}
        <motion.div
          custom={4}
          variants={cardVariants}
          initial="hidden"
          animate="visible"
          className="space-y-3"
        >
          <button
            onClick={() => navigate('/fitness/progress')}
            className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            <TrendingUp size={18} /> Посмотреть прогресс <ArrowRight size={16} />
          </button>
          <button
            onClick={() => navigate('/fitness')}
            className="w-full py-3 rounded-2xl text-sm font-medium border border-white/[0.1]"
            style={{ color: 'var(--app-hint)' }}
          >
            На главную
          </button>
        </motion.div>
      </div>

      {/* ── Модал ввода имени шаблона ── */}
      <AnimatePresence>
        {showTemplateModal && (
          <>
            {/* Оверлей */}
            <motion.div className="fixed inset-0 z-50" style={{ background: 'rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setShowTemplateModal(false)} />
            {/* Bottom-sheet */}
            <motion.div
              className="fixed bottom-0 left-0 right-0 z-[51] rounded-t-[24px] p-4 space-y-4"
              style={{ background: 'var(--glass-bg, #1e1e2e)', borderTop: '1px solid rgba(255,255,255,0.08)' }}
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}>
              {/* Индикатор */}
              <div className="flex justify-center">
                <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.2)' }} />
              </div>
              <h3 className="text-base font-bold flex items-center gap-2" style={{ color: 'var(--app-text)' }}>
                <FileText size={18} style={{ color: '#fb923c' }} />
                Сохранить как шаблон
              </h3>
              {/* Поле имени шаблона */}
              <input
                type="text"
                value={templateName}
                onChange={(e) => setTemplateName(e.target.value)}
                placeholder="Название шаблона..."
                autoFocus
                className="w-full px-4 py-3 rounded-xl text-sm bg-transparent border border-white/[0.1] outline-none"
                style={{ color: 'var(--app-text)' }}
              />
              {/* Превью упражнений */}
              {templateExercises.length > 0 && (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {templateExercises.map((ex, idx) => (
                    <div key={idx} className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                      style={{ background: 'rgba(255,255,255,0.03)' }}>
                      <Dumbbell size={12} style={{ color: '#818cf8' }} />
                      <span className="text-xs flex-1" style={{ color: 'var(--app-text)' }}>
                        {ex.exercise_name}
                      </span>
                      <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                        {ex.sets}×{ex.reps || '—'}
                        {ex.weight_kg ? ` · ${ex.weight_kg} кг` : ''}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {/* Кнопки */}
              <div className="flex gap-3">
                <button onClick={() => setShowTemplateModal(false)}
                  className="flex-1 py-3 rounded-xl text-sm font-medium"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-text)' }}>
                  Отмена
                </button>
                <button onClick={handleSaveTemplate}
                  disabled={!templateName.trim() || createTemplateMut.isPending}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white"
                  style={{
                    background: templateName.trim()
                      ? 'linear-gradient(135deg, #fb923c, #ea580c)'
                      : 'rgba(255,255,255,0.1)',
                    opacity: createTemplateMut.isPending ? 0.6 : 1,
                  }}>
                  <Save size={16} />
                  {createTemplateMut.isPending ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
