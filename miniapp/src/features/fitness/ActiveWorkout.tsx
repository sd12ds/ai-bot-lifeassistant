/**
 * Экран активной тренировки — 3 фазы:
 * 1. setup — подготовка: выбор типа, добавление упражнений, настройка подходов (таймер НЕ тикает)
 * 2. active — тренировка: таймер тикает, отмечаешь подходы, голосовой ввод
 * 3. finishing → WorkoutComplete
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Play, Square, Plus, Trash2, Dumbbell, Timer, ChevronDown, ChevronUp,
  X, Check, Clipboard, Zap, FileText, RefreshCw, Loader2, Save
} from 'lucide-react'
import {
  useStartSession, useAddSet, useFinishSession, useNextWorkout, useTemplates, useCreateTemplate,
  useAiReplaceExercise,
  type Exercise, type WorkoutSet, type Template, type TemplateExercise, type AiAlternative
} from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'
import { ExerciseSearch } from './ExerciseSearch'
import { VoiceButton, type VoiceIntent } from './VoiceButton'

/** Типы тренировок */
const WORKOUT_TYPES = [
  { value: 'strength', label: 'Силовая', icon: '🏋️' },
  { value: 'cardio', label: 'Кардио', icon: '🏃' },
  { value: 'home', label: 'Дом', icon: '🏠' },
  { value: 'stretching', label: 'Растяжка', icon: '🧘' },
]

/** Источники наполнения тренировки */
type WorkoutSource = 'free' | 'program' | 'template'

/** Локальный подход с ключом для React */
interface LocalSet {
  _key: number
  exercise_id: number
  exercise_name: string
  reps: number
  weight_kg: number
  duration_sec: number
  set_type: string
  saved: boolean
  serverSet?: WorkoutSet
}

/** Локальное упражнение с подходами */
interface LocalExercise {
  exercise: Exercise
  sets: LocalSet[]
  collapsed: boolean
}

/** Категории кардио — длительность/дистанция вместо вес/повторы */
const CARDIO_CATEGORIES = new Set(['cardio', 'flexibility'])

/** Проверяет, является ли упражнение кардио/растяжкой */
function isCardioExercise(exercise: Exercise): boolean {
  return CARDIO_CATEGORIES.has(exercise.category || '')
}

export function ActiveWorkout() {
  const navigate = useNavigate()
  const location = useLocation()
  const startSession = useStartSession()
  const addSetMut = useAddSet()
  const finishSession = useFinishSession()

  // Данные программы и шаблонов для фазы setup
  const { data: nextWorkout } = useNextWorkout()
  const { data: templates } = useTemplates()

  // Состояние тренировки
  const [phase, setPhase] = useState<'setup' | 'active' | 'finishing'>('setup')
  const [workoutType, setWorkoutType] = useState('strength')
  const [workoutSource, setWorkoutSource] = useState<WorkoutSource>('free')
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [exercises, setExercises] = useState<LocalExercise[]>([])
  const [showSearch, setShowSearch] = useState(false)
  const [notes, setNotes] = useState('') // Заметки к тренировке
  const [showFinishConfirm, setShowFinishConfirm] = useState(false)
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null)

  // Сохранение набора упражнений как шаблон (без старта тренировки)
  const createTemplateMut = useCreateTemplate()
  const [showSaveTemplate, setShowSaveTemplate] = useState(false)
  const [saveTemplateName, setSaveTemplateName] = useState('')

  // AI замена упражнения — состояние bottom-sheet
  const [replaceExIdx, setReplaceExIdx] = useState<number | null>(null)
  const [replaceAlternatives, setReplaceAlternatives] = useState<AiAlternative[]>([])
  const aiReplace = useAiReplaceExercise()

  // Таймер тренировки (секунды)
  const [elapsed, setElapsed] = useState(0)
  const [timerRunning, setTimerRunning] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Таймер отдыха
  const [restTime, setRestTime] = useState(0)
  const [restRunning, setRestRunning] = useState(false)
  const [restTarget, setRestTarget] = useState(90)
  const restRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Ключ для уникальных id подходов
  const keyRef = useRef(0)
  const nextKey = () => ++keyRef.current

  // ── Сохранить текущие упражнения как шаблон ──────────────────────────────
  const handleSaveAsTemplate = async () => {
    if (!saveTemplateName.trim() || exercises.length === 0) return
    try {
      await createTemplateMut.mutateAsync({
        name: saveTemplateName.trim(),
        description: `${exercises.length} упражнений`,
        exercises: exercises.map((ex) => ({
          exercise_id: ex.exercise.id,
          sets: ex.sets.length,
          reps: ex.sets[0]?.reps || undefined,
          weight_kg: ex.sets[0]?.weight_kg || undefined,
          duration_sec: ex.sets[0]?.duration_sec || undefined,
          rest_sec: 60,
        })),
      })
      setShowSaveTemplate(false)
      setSaveTemplateName('')
    } catch (e) {
      console.error('Ошибка сохранения шаблона:', e)
    }
  }

  // ── Загрузка упражнений из выбранного шаблона ───────────────────────────────
  const loadTemplateExercises = useCallback((tpl: Template) => {
    setSelectedTemplateId(tpl.id)
    if (!tpl.exercises?.length) return
    const loaded: LocalExercise[] = tpl.exercises.map((tex: TemplateExercise) => {
      const isCardio = CARDIO_CATEGORIES.has(tex.exercise_category || '')
      const sets: LocalSet[] = Array.from({ length: tex.sets }, () => ({
        _key: nextKey(),
        exercise_id: tex.exercise_id,
        exercise_name: tex.exercise_name || `Упражнение #${tex.exercise_id}`,
        reps: tex.reps || (isCardio ? 0 : 10),
        weight_kg: tex.weight_kg || 0,
        duration_sec: tex.duration_sec || (isCardio ? 600 : 0),
        set_type: 'working',
        saved: false,
      }))
      return {
        exercise: {
          id: tex.exercise_id,
          name: tex.exercise_name || `Упражнение #${tex.exercise_id}`,
          category: tex.exercise_category || 'strength',
        } as Exercise,
        sets,
        collapsed: false,
      }
    })
    setExercises(loaded)
  }, [])

  // ── Автозагрузка упражнений из программы (при выборе source='program') ──────
  useEffect(() => {
    if (workoutSource !== 'program') return
    if (!nextWorkout?.template_id || !templates?.length) return
    // Ищем шаблон по template_id из активной программы
    const tpl = templates.find((t: Template) => t.id === nextWorkout.template_id)
    if (!tpl || !tpl.exercises?.length) return
    // Формируем список упражнений из шаблона
    const loaded: LocalExercise[] = tpl.exercises.map((tex: TemplateExercise) => {
      const isCardio = CARDIO_CATEGORIES.has(tex.exercise_category || '')
      // Генерируем подходы по количеству sets в шаблоне
      const sets: LocalSet[] = Array.from({ length: tex.sets }, () => ({
        _key: nextKey(),
        exercise_id: tex.exercise_id,
        exercise_name: tex.exercise_name || `Упражнение #${tex.exercise_id}`,
        reps: tex.reps || (isCardio ? 0 : 10),
        weight_kg: tex.weight_kg || 0,
        duration_sec: tex.duration_sec || (isCardio ? 600 : 0),
        set_type: 'working',
        saved: false,
      }))
      return {
        exercise: {
          id: tex.exercise_id,
          name: tex.exercise_name || `Упражнение #${tex.exercise_id}`,
          category: tex.exercise_category || 'strength',
        } as Exercise,
        sets,
        collapsed: false,
      }
    })
    setExercises(loaded)
  }, [workoutSource, nextWorkout, templates])

  // ── Автовыбор source при навигации из ProgramsPage или Templates ─────────
  useEffect(() => {
    const state = location.state as { fromProgram?: boolean; templateId?: number } | null
    // Из программы — источник переключается на 'program', упражнения загрузит следующий эффект
    if (state?.fromProgram && nextWorkout) {
      setWorkoutSource('program')
    }
    // Из страницы шаблонов — сразу загружаем упражнения выбранного шаблона
    if (state?.templateId && templates?.length) {
      const tpl = templates.find((t: Template) => t.id === state.templateId)
      if (tpl) {
        setWorkoutSource('template')
        loadTemplateExercises(tpl)
      }
    }
  }, [location.state, nextWorkout, templates, loadTemplateExercises])

  // ── Таймер тренировки ──────────────────────────────────────────────────────
  useEffect(() => {
    if (timerRunning) {
      intervalRef.current = setInterval(() => setElapsed((s) => s + 1), 1000)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [timerRunning])

  // ── Таймер отдыха ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (restRunning) {
      restRef.current = setInterval(() => {
        setRestTime((t) => {
          if (t + 1 >= restTarget) {
            setRestRunning(false)
            return 0
          }
          return t + 1
        })
      }, 1000)
    }
    return () => { if (restRef.current) clearInterval(restRef.current) }
  }, [restRunning, restTarget])

  // ── Форматирование времени ─────────────────────────────────────────────────
  const formatTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // ── Добавить упражнение ────────────────────────────────────────────────────
  const handleExerciseSelect = useCallback((ex: Exercise) => {
    setExercises((prev) => [
      ...prev,
      {
        exercise: ex,
        sets: [{
          _key: nextKey(),
          exercise_id: ex.id,
          exercise_name: ex.name,
          reps: isCardioExercise(ex) ? 0 : 10,
          weight_kg: 0,
          duration_sec: isCardioExercise(ex) ? 600 : 0,
          set_type: 'working',
          saved: false,
        }],
        collapsed: false,
      },
    ])
    setShowSearch(false)
  }, [])

  // ── Добавить подход к упражнению ───────────────────────────────────────────
  const addLocalSet = (exIdx: number) => {
    setExercises((prev) =>
      prev.map((ex, i) => {
        if (i !== exIdx) return ex
        const lastSet = ex.sets[ex.sets.length - 1]
        return {
          ...ex,
          sets: [...ex.sets, {
            _key: nextKey(),
            exercise_id: ex.exercise.id,
            exercise_name: ex.exercise.name,
            reps: lastSet?.reps || (isCardioExercise(ex.exercise) ? 0 : 10),
            weight_kg: lastSet?.weight_kg || 0,
            duration_sec: lastSet?.duration_sec || (isCardioExercise(ex.exercise) ? 600 : 0),
            set_type: 'working',
            saved: false,
          }],
        }
      })
    )
  }

  // ── Сохранить подход на сервере ────────────────────────────────────────────
  const saveSet = async (exIdx: number, setIdx: number) => {
    if (!sessionId) return
    const set = exercises[exIdx].sets[setIdx]
    if (set.saved) return

    try {
      const result = await addSetMut.mutateAsync({
        sessionId,
        dto: {
          exercise_id: set.exercise_id,
          reps: set.reps || undefined,
          weight_kg: set.weight_kg || undefined,
          duration_sec: set.duration_sec || undefined,
          set_type: set.set_type,
        },
      })
      // Обновляем подход как сохранённый
      setExercises((prev) =>
        prev.map((ex, i) => {
          if (i !== exIdx) return ex
          return {
            ...ex,
            sets: ex.sets.map((s, si) =>
              si === setIdx ? { ...s, saved: true, serverSet: result } : s
            ),
          }
        })
      )
      // Запуск таймера отдыха
      setRestTime(0)
      setRestRunning(true)
    } catch (e) {
      console.error('Ошибка сохранения подхода:', e)
    }
  }

  // ── Обновить поле подхода ──────────────────────────────────────────────────
  const updateSet = (exIdx: number, setIdx: number, field: string, value: number) => {
    setExercises((prev) =>
      prev.map((ex, i) => {
        if (i !== exIdx) return ex
        return {
          ...ex,
          sets: ex.sets.map((s, si) =>
            si === setIdx ? { ...s, [field]: value } : s
          ),
        }
      })
    )
  }

  // ── Удалить упражнение ─────────────────────────────────────────────────────
  const removeExercise = (exIdx: number) => {
    setExercises((prev) => prev.filter((_, i) => i !== exIdx))
  }

  // ── Свернуть/развернуть ────────────────────────────────────────────────────
  const toggleCollapse = (exIdx: number) => {
    setExercises((prev) =>
      prev.map((ex, i) =>
        i === exIdx ? { ...ex, collapsed: !ex.collapsed } : ex
      )
    )
  }

  // ── Старт тренировки (переход из setup → active) ──────────────────────────
  const handleStart = async () => {
    try {
      // Название сессии: для программы — название дня, для свободной —
      // не передаём (finish_workout авто-генерирует из упражнений)
      let sessionName: string | undefined
      if (workoutSource === 'program' && nextWorkout) {
        sessionName = nextWorkout.day_name || `День ${nextWorkout.day_number}`
      }

      const session = await startSession.mutateAsync({
        workout_type: workoutType,
        ...(sessionName ? { name: sessionName } : {}),
      })
      setSessionId(session.id)
      setPhase('active')
      setTimerRunning(true)
    } catch (e) {
      console.error('Ошибка старта тренировки:', e)
    }
  }

  // ── Завершить тренировку ───────────────────────────────────────────────────
  const handleFinish = async () => {
    if (!sessionId) return
    setPhase('finishing')
    setTimerRunning(false)
    setRestRunning(false)

    try {
      // Автосохраняем все несохранённые подходы перед завершением.
      // Пользователь мог не нажать ✓ вручную — сохраняем все параллельно.
      const unsavedTasks = exercises.flatMap((ex) =>
        ex.sets
          .filter((set) => !set.saved)
          .map((set) =>
            addSetMut.mutateAsync({
              sessionId,
              dto: {
                exercise_id: set.exercise_id,
                reps: set.reps || undefined,
                weight_kg: set.weight_kg || undefined,
                duration_sec: set.duration_sec || undefined,
                set_type: set.set_type,
              },
            }).catch((e) => {
              // Не прерываем завершение при ошибке отдельного подхода
              console.warn('Не удалось сохранить подход:', e)
            })
          )
      )
      if (unsavedTasks.length > 0) {
        await Promise.all(unsavedTasks)
      }

      const result = await finishSession.mutateAsync({
        sessionId,
        dto: { notes },
      })

      // Считаем итоговые данные (включая только что сохранённые подходы)
      const allSets = exercises.flatMap((ex) => ex.sets)
      const totalSetsCount = allSets.length
      const totalVolumeCalc = allSets.reduce((s, st) => s + (st.reps || 0) * (st.weight_kg || 0), 0)

      navigate('/fitness/complete', {
        state: {
          session: result,
          elapsed,
          exerciseCount: exercises.length,
          totalSets: totalSetsCount,
          totalVolume: totalVolumeCalc,
          // Данные упражнений для сохранения как шаблон
          exercises: exercises.map((ex) => ({
            exercise_id: ex.exercise.id,
            exercise_name: ex.exercise.name,
            exercise_category: ex.exercise.category || "strength",
            sets: ex.sets.length,
            reps: ex.sets[0]?.reps || null,
            weight_kg: ex.sets[0]?.weight_kg || null,
            duration_sec: ex.sets[0]?.duration_sec || null,
            rest_sec: 60,
          })),
        },
      })
    } catch (e) {
      console.error('Ошибка завершения:', e)
      setPhase('active')
      setTimerRunning(true)
    }
  }


  // ── AI замена упражнения ─────────────────────────────────────────────────
  const handleAiReplace = async (exIdx: number) => {
    const ex = exercises[exIdx]
    if (!ex) return
    setReplaceExIdx(exIdx)
    setReplaceAlternatives([])
    try {
      const result = await aiReplace.mutateAsync({ exercise_id: ex.exercise.id })
      setReplaceAlternatives(result.alternatives || [])
    } catch (e) {
      console.error('Ошибка AI замены:', e)
    }
  }

  // Применить замену — заменяет упражнение в списке
  const applyReplacement = (altExId: number, altExName: string) => {
    if (replaceExIdx === null) return
    setExercises((prev) =>
      prev.map((ex, i) => {
        if (i !== replaceExIdx) return ex
        // Создаём новое упражнение с теми же подходами
        const newExercise: Exercise = {
          ...ex.exercise,
          id: altExId,
          name: altExName,
        }
        return {
          ...ex,
          exercise: newExercise,
          sets: ex.sets.map((s) => ({
            ...s,
            exercise_id: altExId,
            exercise_name: altExName,
            saved: false, // Сбрасываем сохранение — нужно пересохранить с новым exercise_id
          })),
        }
      })
    )
    setReplaceExIdx(null)
    setReplaceAlternatives([])
  }

  // ── Обработка голосовых команд ─────────────────────────────────────────────
  const handleVoiceIntent = useCallback((result: VoiceIntent) => {
    const { intent, params } = result
    switch (intent) {
      case 'add_set': {
        // Записать подход к последнему упражнению
        if (exercises.length === 0) break
        const lastExIdx = exercises.length - 1
        const lastEx = exercises[lastExIdx]
        // Находим первый несохранённый подход или добавляем новый
        const unfinishedIdx = lastEx.sets.findIndex((s) => !s.saved)
        if (unfinishedIdx >= 0) {
          // Обновляем поля несохранённого подхода и сохраняем
          if (params.weight_kg) updateSet(lastExIdx, unfinishedIdx, 'weight_kg', params.weight_kg)
          if (params.reps) updateSet(lastExIdx, unfinishedIdx, 'reps', params.reps)
          // Небольшая задержка для обновления стейта, затем сохраняем
          setTimeout(() => saveSet(lastExIdx, unfinishedIdx), 100)
        } else {
          // Все подходы сохранены — добавляем новый
          addLocalSet(lastExIdx)
          setTimeout(() => {
            const newSetIdx = exercises[lastExIdx].sets.length // индекс нового подхода
            if (params.weight_kg) updateSet(lastExIdx, newSetIdx, 'weight_kg', params.weight_kg)
            if (params.reps) updateSet(lastExIdx, newSetIdx, 'reps', params.reps)
            setTimeout(() => saveSet(lastExIdx, newSetIdx), 100)
          }, 50)
        }
        break
      }
      case 'add_exercise': {
        // Открыть поиск упражнений (пользователь выберет из результатов)
        setShowSearch(true)
        break
      }
      case 'rest_timer': {
        // Запустить таймер отдыха
        const sec = params.seconds || 90
        setRestTarget(sec)
        setRestTime(0)
        setRestRunning(true)
        break
      }
      case 'finish': {
        // Показать диалог завершения
        setShowFinishConfirm(true)
        break
      }
    }
  }, [exercises, updateSet, saveSet, addLocalSet])

  // ── Подсчёт суммарных данных ───────────────────────────────────────────────
  const totalSavedSets = exercises.reduce((s, ex) => s + ex.sets.filter((st) => st.saved).length, 0)
  // Макс. рабочий вес среди всех сохранённых подходов
  const maxWeight = exercises.reduce(
    (m, ex) => Math.max(m, ...ex.sets.filter((st) => st.saved).map((st) => st.weight_kg || 0)), 0
  )

  // ══════════════════════════════════════════════════════════════════════════════
  // ФАЗА SETUP — подготовка тренировки (таймер НЕ тикает)
  // ══════════════════════════════════════════════════════════════════════════════
  if (phase === 'setup') {
    return (<>
      <div className="h-full flex flex-col overflow-hidden">
        {/* Шапка */}
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>
            Новая тренировка
          </h1>
          <button onClick={() => navigate('/fitness')} className="p-2">
            <X size={22} style={{ color: 'var(--app-hint)' }} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
          {/* Выбор типа тренировки */}
          <div>
            <p className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>
              Тип тренировки
            </p>
            <div className="grid grid-cols-4 gap-2">
              {WORKOUT_TYPES.map((wt) => (
                <button
                  key={wt.value}
                  onClick={() => setWorkoutType(wt.value)}
                  className="flex flex-col items-center gap-1 py-2 rounded-xl text-xs font-medium transition-colors"
                  style={{
                    background: workoutType === wt.value
                      ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                    border: workoutType === wt.value
                      ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.08)',
                    color: workoutType === wt.value ? '#a5b4fc' : 'var(--app-text)',
                  }}
                >
                  <span className="text-xl">{wt.icon}</span>
                  {wt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Источник тренировки: свободная / из программы / из шаблона */}
          <div>
            <p className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>
              Наполнение
            </p>
            <div className="grid grid-cols-3 gap-2">
              {/* Свободная */}
              <button
                onClick={() => { setWorkoutSource('free'); setExercises([]) }}
                className="flex items-center gap-2 p-3 rounded-xl text-xs font-medium transition-colors"
                style={{
                  background: workoutSource === 'free' ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.04)',
                  border: workoutSource === 'free' ? '1px solid rgba(34,197,94,0.3)' : '1px solid rgba(255,255,255,0.08)',
                  color: workoutSource === 'free' ? '#4ade80' : 'var(--app-text)',
                }}
              >
                <Zap size={16} />
                Свободная
              </button>
              {/* Из программы */}
              <button
                onClick={() => setWorkoutSource('program')}
                disabled={!nextWorkout}
                className="flex items-center gap-2 p-3 rounded-xl text-xs font-medium transition-colors"
                style={{
                  background: workoutSource === 'program' ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                  border: workoutSource === 'program' ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.08)',
                  color: workoutSource === 'program' ? '#a5b4fc' : 'var(--app-text)',
                  opacity: nextWorkout ? 1 : 0.4,
                }}
              >
                <Clipboard size={16} />
                Программа
              </button>
              {/* Из шаблона */}
              <button
                onClick={() => setWorkoutSource('template')}
                disabled={!templates?.length}
                className="flex items-center gap-2 p-3 rounded-xl text-xs font-medium transition-colors"
                style={{
                  background: workoutSource === 'template' ? 'rgba(251,146,60,0.15)' : 'rgba(255,255,255,0.04)',
                  border: workoutSource === 'template' ? '1px solid rgba(251,146,60,0.3)' : '1px solid rgba(255,255,255,0.08)',
                  color: workoutSource === 'template' ? '#fb923c' : 'var(--app-text)',
                  opacity: templates?.length ? 1 : 0.4,
                }}
              >
                <FileText size={16} />
                Шаблон
              </button>
            </div>
          </div>

          {/* Информация об источнике */}
          {workoutSource === 'program' && nextWorkout && (
            <GlassCard className="!p-3">
              <div className="text-xs font-medium mb-1" style={{ color: '#a5b4fc' }}>
                📋 {nextWorkout.program_name}
              </div>
              <div className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                День {nextWorkout.day_number}: {nextWorkout.day_name || `День ${nextWorkout.day_number}`}
              </div>
              <div className="text-xs mt-1" style={{ color: 'var(--app-hint)' }}>
                Прогресс: {nextWorkout.completed_workouts}/{nextWorkout.total_days}
              </div>
            </GlassCard>
          )}

          {workoutSource === 'template' && templates && templates.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                Выбери шаблон для загрузки упражнений
              </p>
              {templates.map((tpl) => {
                const isSelected = selectedTemplateId === tpl.id
                return (
                  <GlassCard key={tpl.id} noPadding>
                    {/* Заголовок шаблона — клик выбирает и загружает упражнения */}
                    <button
                      onClick={() => loadTemplateExercises(tpl)}
                      className="w-full flex items-center justify-between p-3"
                      style={{
                        borderLeft: isSelected ? '3px solid #fb923c' : '3px solid transparent',
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-10 h-10 rounded-xl flex items-center justify-center"
                          style={{
                            background: isSelected
                              ? 'linear-gradient(135deg, rgba(251,146,60,0.3), rgba(234,88,12,0.2))'
                              : 'linear-gradient(135deg, rgba(251,146,60,0.12), rgba(234,88,12,0.06))',
                          }}
                        >
                          <FileText size={18} style={{ color: '#fb923c' }} />
                        </div>
                        <div className="text-left">
                          <div className="text-sm font-medium" style={{ color: isSelected ? '#fb923c' : 'var(--app-text)' }}>
                            {tpl.name}
                          </div>
                          <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                            {tpl.exercises?.length || 0} упражнений
                            {tpl.description ? ` · ${tpl.description}` : ''}
                          </div>
                        </div>
                      </div>
                      {isSelected && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                          style={{ background: 'rgba(251,146,60,0.2)', color: '#fb923c' }}>
                          Выбран ✓
                        </span>
                      )}
                    </button>
                    {/* Превью упражнений — всегда видно */}
                    {tpl.exercises && tpl.exercises.length > 0 && (
                      <div className="px-3 pb-3 space-y-1">
                        {tpl.exercises.map((ex, idx) => (
                          <div key={ex.id || idx}
                            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg"
                            style={{ background: 'rgba(255,255,255,0.03)' }}>
                            <Dumbbell size={12} style={{ color: '#818cf8' }} />
                            <span className="text-xs flex-1" style={{ color: 'var(--app-text)' }}>
                              {ex.exercise_name || `Упражнение #${ex.exercise_id}`}
                            </span>
                            <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                              {ex.sets}×{ex.reps || '—'}
                              {ex.weight_kg ? ` · ${ex.weight_kg} кг` : ''}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </GlassCard>
                )
              })}
            </div>
          )}

          {/* Поиск упражнений (полноэкранный) */}
          <AnimatePresence>
            {showSearch && (
              <motion.div
                className="fixed inset-0 z-50 flex flex-col"
                style={{ background: 'var(--app-bg)' }}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 20 }}
              >
                <div className="flex-1 p-4">
                  <ExerciseSearch
                    onSelect={handleExerciseSelect}
                    onClose={() => setShowSearch(false)}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Список добавленных упражнений */}
          {exercises.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                Упражнения ({exercises.length})
              </p>
              {exercises.map((ex, exIdx) => (
                <GlassCard key={`${ex.exercise.id}-${exIdx}`} noPadding>
                  {/* Заголовок */}
                  <button
                    onClick={() => toggleCollapse(exIdx)}
                    className="w-full flex items-center justify-between p-3"
                  >
                    <div className="flex items-center gap-2">
                      <Dumbbell size={16} style={{ color: '#818cf8' }} />
                      <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                        {ex.exercise.name}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 rounded-full"
                        style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}>
                        {ex.sets.length} подх
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={(e) => { e.stopPropagation(); removeExercise(exIdx) }} className="p-1">
                        <Trash2 size={14} style={{ color: 'var(--app-hint)' }} />
                      </button>
                      {ex.collapsed
                        ? <ChevronDown size={16} style={{ color: 'var(--app-hint)' }} />
                        : <ChevronUp size={16} style={{ color: 'var(--app-hint)' }} />}
                    </div>
                  </button>
                  {/* Подходы (настройка — можно менять вес/повторы до старта) */}
                  {!ex.collapsed && (
                    <div className="px-3 pb-3">
                      <div className="grid grid-cols-[28px_1fr_1fr_36px] gap-2 text-[10px] px-1 mb-1"
                        style={{ color: 'var(--app-hint)' }}>
                        <span>#</span>
                        {isCardioExercise(ex.exercise) ? (
                          <><span>Время (мин)</span><span>Дистанция (км)</span></>
                        ) : (
                          <><span>Вес (кг)</span><span>Повторы</span></>
                        )}
                        <span />
                      </div>
                      <div className="space-y-1.5">
                        {ex.sets.map((set, setIdx) => (
                          <div key={set._key} className="grid grid-cols-[28px_1fr_1fr_36px] gap-2 items-center">
                            <span className="text-xs text-center" style={{ color: 'var(--app-hint)' }}>
                              {setIdx + 1}
                            </span>
                            {isCardioExercise(ex.exercise) ? (
                              <>
                                <input type="number"
                                  value={set.duration_sec ? Math.round(set.duration_sec / 60) : ''}
                                  onChange={(e) => updateSet(exIdx, setIdx, 'duration_sec', (parseFloat(e.target.value) || 0) * 60)}
                                  className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                  style={{ color: 'var(--app-text)' }} placeholder="0" inputMode="decimal" />
                                <input type="number"
                                  value={set.weight_kg || ''}
                                  onChange={(e) => updateSet(exIdx, setIdx, 'weight_kg', parseFloat(e.target.value) || 0)}
                                  className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                  style={{ color: 'var(--app-text)' }} placeholder="0" inputMode="decimal" />
                              </>
                            ) : (
                              <>
                                <input type="number"
                                  value={set.weight_kg || ''}
                                  onChange={(e) => updateSet(exIdx, setIdx, 'weight_kg', parseFloat(e.target.value) || 0)}
                                  className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                  style={{ color: 'var(--app-text)' }} placeholder="0" inputMode="decimal" />
                                <input type="number"
                                  value={set.reps || ''}
                                  onChange={(e) => updateSet(exIdx, setIdx, 'reps', parseInt(e.target.value) || 0)}
                                  className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                                  style={{ color: 'var(--app-text)' }} placeholder="0" inputMode="numeric" />
                              </>
                            )}
                            <button onClick={() => {
                              setExercises(prev => prev.map((ex2, i) =>
                                i !== exIdx ? ex2 : { ...ex2, sets: ex2.sets.filter((_, si) => si !== setIdx) }
                              ))
                            }} className="w-8 h-8 flex items-center justify-center">
                              <X size={14} style={{ color: 'var(--app-hint)' }} />
                            </button>
                          </div>
                        ))}
                      </div>
                      <button onClick={() => addLocalSet(exIdx)}
                        className="flex items-center gap-1 mt-2 text-xs font-medium px-2 py-1 rounded-lg"
                        style={{ color: '#818cf8' }}>
                        <Plus size={14} /> Подход
                      </button>
                    </div>
                  )}
                </GlassCard>
              ))}
            </div>
          )}

          {/* Кнопка добавить упражнение */}
          <button
            onClick={() => setShowSearch(true)}
            className="w-full flex items-center justify-center gap-2 py-4 rounded-2xl border border-dashed border-white/[0.15] text-sm font-medium"
            style={{ color: '#818cf8' }}
          >
            <Plus size={18} /> Добавить упражнение
          </button>

          {/* Кнопка СТАРТ */}
          {/* Подсказка: добавь все упражнения перед стартом */}
          {exercises.length === 0 && (
            <p className="text-xs text-center" style={{ color: 'var(--app-hint)' }}>
              Добавь все упражнения и настрой подходы, затем нажми «Старт»
            </p>
          )}

          {/* Кнопки: Старт + Сохранить шаблон */}
          <div className="space-y-2">
            {/* Кнопка Старт — запускает таймер и переводит в активную фазу */}
            <button
              onClick={handleStart}
              disabled={startSession.isPending || exercises.length === 0}
              className="w-full py-4 rounded-2xl text-base font-bold text-white flex items-center justify-center gap-2"
              style={{
                background: exercises.length > 0
                  ? 'linear-gradient(135deg, #22c55e, #16a34a)'
                  : 'rgba(255,255,255,0.1)',
                opacity: startSession.isPending ? 0.6 : 1,
              }}
            >
              <Play size={20} />
              {startSession.isPending ? 'Запуск...' : `▶ Старт тренировки (${exercises.length} упр)`}
            </button>

            {/* Кнопка сохранить как шаблон — видна когда есть упражнения */}
            {exercises.length > 0 && (
              <button
                onClick={() => { setSaveTemplateName(''); setShowSaveTemplate(true) }}
                className="w-full py-3 rounded-2xl text-sm font-medium flex items-center justify-center gap-2 border border-white/[0.1]"
                style={{ color: '#fb923c' }}
              >
                <Save size={16} /> Сохранить как шаблон
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Модал сохранения шаблона (setup фаза) ── */}
      <AnimatePresence>
        {showSaveTemplate && (
          <>
            <motion.div className="fixed inset-0 z-50" style={{ background: 'rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setShowSaveTemplate(false)} />
            <motion.div
              className="fixed bottom-0 left-0 right-0 z-[51] rounded-t-[24px] p-4 space-y-4"
              style={{ background: 'var(--glass-bg, #1e1e2e)', borderTop: '1px solid rgba(255,255,255,0.08)' }}
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}>
              <div className="flex justify-center">
                <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.2)' }} />
              </div>
              <h3 className="text-base font-bold flex items-center gap-2" style={{ color: 'var(--app-text)' }}>
                <FileText size={18} style={{ color: '#fb923c' }} />
                Сохранить шаблон
              </h3>
              <input
                type="text"
                value={saveTemplateName}
                onChange={(e) => setSaveTemplateName(e.target.value)}
                placeholder="Название шаблона..."
                autoFocus
                className="w-full px-4 py-3 rounded-xl text-sm bg-transparent border border-white/[0.1] outline-none"
                style={{ color: 'var(--app-text)' }}
              />
              {/* Превью упражнений */}
              <div className="space-y-1 max-h-40 overflow-y-auto">
                {exercises.map((ex, idx) => (
                  <div key={idx} className="flex items-center gap-2 px-3 py-1.5 rounded-lg"
                    style={{ background: 'rgba(255,255,255,0.03)' }}>
                    <Dumbbell size={12} style={{ color: '#818cf8' }} />
                    <span className="text-xs flex-1" style={{ color: 'var(--app-text)' }}>
                      {ex.exercise.name}
                    </span>
                    <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                      {ex.sets.length}×{ex.sets[0]?.reps || '—'}
                      {ex.sets[0]?.weight_kg ? ` · ${ex.sets[0].weight_kg} кг` : ''}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex gap-3">
                <button onClick={() => setShowSaveTemplate(false)}
                  className="flex-1 py-3 rounded-xl text-sm font-medium"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-text)' }}>
                  Отмена
                </button>
                <button onClick={handleSaveAsTemplate}
                  disabled={!saveTemplateName.trim() || createTemplateMut.isPending}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white"
                  style={{
                    background: saveTemplateName.trim()
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
    </>)
  }

  // ══════════════════════════════════════════════════════════════════════════════
  // ФАЗА ACTIVE — тренировка идёт
  // ══════════════════════════════════════════════════════════════════════════════
  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка с таймером */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
            {WORKOUT_TYPES.find((w) => w.value === workoutType)?.icon}{' '}
            {WORKOUT_TYPES.find((w) => w.value === workoutType)?.label || 'Тренировка'}
          </h1>
          <button
            onClick={() => setShowFinishConfirm(true)}
            disabled={phase === 'finishing'}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-sm font-bold text-white"
            style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)' }}
          >
            <Square size={14} /> Завершить
          </button>
        </div>

        {/* Основной таймер */}
        <GlassCard className="flex items-center justify-between !py-3">
          <div className="flex items-center gap-3">
            <Timer size={20} style={{ color: '#818cf8' }} />
            <span className="text-2xl font-mono font-bold" style={{ color: 'var(--app-text)' }}>
              {formatTime(elapsed)}
            </span>
          </div>
          <div className="flex gap-4 text-xs" style={{ color: 'var(--app-hint)' }}>
            <div className="text-center">
              <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                {totalSavedSets}
              </div>
              подх
            </div>
            {maxWeight > 0 && (
              <div className="text-center">
                <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  {maxWeight}
                </div>
                кг
              </div>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Таймер отдыха */}
      <AnimatePresence>
        {restRunning && (
          <motion.div className="mx-4 mb-2"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}>
            <div className="flex items-center justify-between px-4 py-3 rounded-2xl"
              style={{ background: 'rgba(251,146,60,0.15)', border: '1px solid rgba(251,146,60,0.3)' }}>
              <div className="flex items-center gap-2">
                <span className="text-lg">⏱️</span>
                <span className="text-sm font-medium" style={{ color: '#fb923c' }}>Отдых</span>
              </div>
              <span className="text-lg font-mono font-bold" style={{ color: '#fb923c' }}>
                {formatTime(restTarget - restTime)}
              </span>
              <button onClick={() => { setRestRunning(false); setRestTime(0) }}
                className="px-3 py-1 rounded-lg text-xs font-medium"
                style={{ background: 'rgba(251,146,60,0.2)', color: '#fb923c' }}>
                Пропустить
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Контент: упражнения */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-3">
        {/* Поиск упражнений */}
        <AnimatePresence>
          {showSearch && (
            <motion.div className="fixed inset-0 z-50 flex flex-col"
              style={{ background: 'var(--app-bg)' }}
              initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}>
              <div className="flex-1 p-4">
                <ExerciseSearch onSelect={handleExerciseSelect} onClose={() => setShowSearch(false)} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Список упражнений */}
        {exercises.map((ex, exIdx) => (
          <GlassCard key={`${ex.exercise.id}-${exIdx}`} noPadding>
            <button onClick={() => toggleCollapse(exIdx)} className="w-full flex items-center justify-between p-3">
              <div className="flex items-center gap-2">
                <Dumbbell size={16} style={{ color: '#818cf8' }} />
                <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                  {ex.exercise.name}
                </span>
                <span className="text-xs px-1.5 py-0.5 rounded-full"
                  style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}>
                  {ex.sets.filter((s) => s.saved).length}/{ex.sets.length}
                </span>
              </div>
              <div className="flex items-center gap-1">
                {/* Кнопка AI замены */}
                <button onClick={(e) => { e.stopPropagation(); handleAiReplace(exIdx) }} className="p-1"
                  title="AI замена">
                  <RefreshCw size={14} style={{ color: '#fb923c' }} />
                </button>
                <button onClick={(e) => { e.stopPropagation(); removeExercise(exIdx) }} className="p-1">
                  <Trash2 size={14} style={{ color: 'var(--app-hint)' }} />
                </button>
                {ex.collapsed
                  ? <ChevronDown size={16} style={{ color: 'var(--app-hint)' }} />
                  : <ChevronUp size={16} style={{ color: 'var(--app-hint)' }} />}
              </div>
            </button>
            {!ex.collapsed && (
              <div className="px-3 pb-3">
                <div className="grid grid-cols-[28px_1fr_1fr_36px] gap-2 text-[10px] px-1 mb-1"
                  style={{ color: 'var(--app-hint)' }}>
                  <span>#</span>
                  {isCardioExercise(ex.exercise) ? (
                    <><span>Время (мин)</span><span>Дистанция (км)</span></>
                  ) : (
                    <><span>Вес (кг)</span><span>Повторы</span></>
                  )}
                  <span />
                </div>
                <div className="space-y-1.5">
                  {ex.sets.map((set, setIdx) => (
                    <div key={set._key} className="grid grid-cols-[28px_1fr_1fr_36px] gap-2 items-center">
                      <span className="text-xs text-center" style={{
                        color: set.saved ? '#22c55e' : 'var(--app-hint)'
                      }}>
                        {set.saved ? '✓' : setIdx + 1}
                      </span>
                      {isCardioExercise(ex.exercise) ? (
                        <>
                          <input type="number"
                            value={set.duration_sec ? Math.round(set.duration_sec / 60) : ''}
                            onChange={(e) => updateSet(exIdx, setIdx, 'duration_sec', (parseFloat(e.target.value) || 0) * 60)}
                            disabled={set.saved}
                            className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                            style={{ color: set.saved ? 'var(--app-hint)' : 'var(--app-text)', opacity: set.saved ? 0.6 : 1 }}
                            placeholder="0" inputMode="decimal" />
                          <input type="number"
                            value={set.weight_kg || ''}
                            onChange={(e) => updateSet(exIdx, setIdx, 'weight_kg', parseFloat(e.target.value) || 0)}
                            disabled={set.saved}
                            className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                            style={{ color: set.saved ? 'var(--app-hint)' : 'var(--app-text)', opacity: set.saved ? 0.6 : 1 }}
                            placeholder="0" inputMode="decimal" />
                        </>
                      ) : (
                        <>
                          <input type="number"
                            value={set.weight_kg || ''}
                            onChange={(e) => updateSet(exIdx, setIdx, 'weight_kg', parseFloat(e.target.value) || 0)}
                            disabled={set.saved}
                            className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                            style={{ color: set.saved ? 'var(--app-hint)' : 'var(--app-text)', opacity: set.saved ? 0.6 : 1 }}
                            placeholder="0" inputMode="decimal" />
                          <input type="number"
                            value={set.reps || ''}
                            onChange={(e) => updateSet(exIdx, setIdx, 'reps', parseInt(e.target.value) || 0)}
                            disabled={set.saved}
                            className="w-full px-2 py-1.5 rounded-lg text-sm bg-transparent border border-white/[0.08] text-center outline-none"
                            style={{ color: set.saved ? 'var(--app-hint)' : 'var(--app-text)', opacity: set.saved ? 0.6 : 1 }}
                            placeholder="0" inputMode="numeric" />
                        </>
                      )}
                      {!set.saved ? (
                        <button onClick={() => saveSet(exIdx, setIdx)}
                          disabled={addSetMut.isPending}
                          className="w-8 h-8 flex items-center justify-center rounded-lg"
                          style={{ background: 'rgba(34,197,94,0.15)' }}>
                          <Check size={16} style={{ color: '#22c55e' }} />
                        </button>
                      ) : (
                        <div className="w-8 h-8 flex items-center justify-center">
                          {set.serverSet?.is_personal_record && <span className="text-xs">🏆</span>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <button onClick={() => addLocalSet(exIdx)}
                  className="flex items-center gap-1 mt-2 text-xs font-medium px-2 py-1 rounded-lg"
                  style={{ color: '#818cf8' }}>
                  <Plus size={14} /> Подход
                </button>
              </div>
            )}
          </GlassCard>
        ))}

        {/* Добавить упражнение */}
        <button onClick={() => setShowSearch(true)}
          className="w-full flex items-center justify-center gap-2 py-4 rounded-2xl border border-dashed border-white/[0.15] text-sm font-medium"
          style={{ color: '#818cf8' }}>
          <Plus size={18} /> Добавить упражнение
        </button>

        {/* Настройка таймера отдыха */}
        <GlassCard className="flex items-center justify-between !py-3">
          <div className="flex items-center gap-2">
            <span>⏱️</span>
            <span className="text-sm" style={{ color: 'var(--app-text)' }}>Отдых</span>
          </div>
          <div className="flex items-center gap-2">
            {[60, 90, 120, 180].map((sec) => (
              <button key={sec} onClick={() => setRestTarget(sec)}
                className="px-2 py-1 rounded-lg text-xs font-medium"
                style={{
                  background: restTarget === sec ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                  color: restTarget === sec ? '#a5b4fc' : 'var(--app-hint)',
                }}>
                {sec >= 60 ? `${sec / 60}м` : `${sec}с`}
              </button>
            ))}
          </div>
        </GlassCard>
      </div>

      {/* Кнопка голосового ввода — только в фазе active */}
      <VoiceButton onIntent={handleVoiceIntent} />

      {/* Bottom-sheet AI замены упражнения */}
      <AnimatePresence>
        {replaceExIdx !== null && (
          <>
            <motion.div className="fixed inset-0 z-50" style={{ background: 'rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => { setReplaceExIdx(null); setReplaceAlternatives([]) }} />
            <motion.div
              className="fixed bottom-0 left-0 right-0 z-[51] rounded-t-[24px] p-4 space-y-3"
              style={{ background: 'var(--glass-bg)', borderTop: '1px solid rgba(255,255,255,0.08)' }}
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}>
              <div className="flex justify-center">
                <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.2)' }} />
              </div>
              <h3 className="text-base font-bold flex items-center gap-2" style={{ color: 'var(--app-text)' }}>
                <RefreshCw size={18} style={{ color: '#fb923c' }} />
                Замена: {exercises[replaceExIdx]?.exercise.name}
              </h3>
              {/* Загрузка */}
              {aiReplace.isPending && (
                <div className="flex items-center justify-center py-6">
                  <Loader2 size={24} className="animate-spin" style={{ color: '#fb923c' }} />
                  <span className="ml-2 text-sm" style={{ color: 'var(--app-hint)' }}>Подбираю альтернативы...</span>
                </div>
              )}
              {/* Альтернативы */}
              {replaceAlternatives.length > 0 && (
                <div className="space-y-2">
                  {replaceAlternatives.map((alt, idx) => (
                    <button
                      key={idx}
                      onClick={() => applyReplacement(alt.exercise_id, alt.exercise_name)}
                      className="w-full text-left p-3 rounded-xl transition-colors"
                      style={{ background: 'rgba(251,146,60,0.08)', border: '1px solid rgba(251,146,60,0.15)' }}
                    >
                      <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                        {alt.exercise_name}
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--app-hint)' }}>
                        {alt.reason}
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {/* Ошибка */}
              {aiReplace.isError && (
                <p className="text-sm text-center" style={{ color: '#ef4444' }}>
                  Ошибка подбора альтернатив
                </p>
              )}
              <button onClick={() => { setReplaceExIdx(null); setReplaceAlternatives([]) }}
                className="w-full py-3 rounded-xl text-sm font-medium"
                style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-text)' }}>
                Отмена
              </button>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Диалог завершения с заметками */}
      <AnimatePresence>
        {showFinishConfirm && (
          <>
            <motion.div className="fixed inset-0 z-50" style={{ background: 'rgba(0,0,0,0.6)' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setShowFinishConfirm(false)} />
            <motion.div
              className="fixed bottom-0 left-0 right-0 z-[51] rounded-t-[24px] p-4 space-y-4"
              style={{ background: 'var(--glass-bg)', borderTop: '1px solid rgba(255,255,255,0.08)' }}
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}>
              <div className="flex justify-center">
                <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.2)' }} />
              </div>
              <h3 className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
                Завершить тренировку?
              </h3>
              <div className="flex gap-4 text-xs" style={{ color: 'var(--app-hint)' }}>
                <span>⏱ {formatTime(elapsed)}</span>
                <span>💪 {totalSavedSets} подх</span>
                {maxWeight > 0 && <span>🏋️ {maxWeight} кг</span>}
              </div>
              {/* Поле заметок */}
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Заметки к тренировке (самочувствие, комментарий)..."
                className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none resize-none"
                style={{ color: 'var(--app-text)', minHeight: '80px' }}
              />
              <div className="flex gap-3">
                <button onClick={() => setShowFinishConfirm(false)}
                  className="flex-1 py-3 rounded-xl text-sm font-medium"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-text)' }}>
                  Отмена
                </button>
                <button onClick={handleFinish}
                  disabled={finishSession.isPending}
                  className="flex-1 py-3 rounded-xl text-sm font-bold text-white"
                  style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)' }}>
                  {finishSession.isPending ? 'Сохранение...' : 'Завершить'}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
