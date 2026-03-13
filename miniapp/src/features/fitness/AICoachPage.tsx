/**
 * Экран AI Coach — 4 действия:
 * 1. Собрать тренировку по группам мышц
 * 2. Заменить упражнение (поиск + альтернативы)
 * 3. Анализ прогресса
 * 4. Рекомендации на неделю
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Sparkles, Dumbbell, RefreshCw, TrendingUp, Lightbulb, Loader2, ChevronDown } from 'lucide-react'
import {
  useAiBuildWorkout, useAiReplaceExercise, useAiAnalyzeProgress, useAiRecommendations,
  useExerciseSearch, useFitnessGoals,
  type AiBuildWorkoutOut, type AiReplaceExerciseOut, type AiAnalyzeProgressOut, type AiRecommendationsOut,
} from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'

/** Группы мышц для выбора */
const MUSCLE_GROUPS = [
  { value: 'chest', label: 'Грудь', icon: '🫁' },
  { value: 'back', label: 'Спина', icon: '🔙' },
  { value: 'legs', label: 'Ноги', icon: '🦵' },
  { value: 'shoulders', label: 'Плечи', icon: '💪' },
  { value: 'arms', label: 'Руки', icon: '🦾' },
  { value: 'core', label: 'Кор', icon: '🎯' },
]

/** Уровни сложности */
const DIFFICULTY_OPTIONS = [
  { value: 'beginner', label: 'Начинающий' },
  { value: 'intermediate', label: 'Средний' },
  { value: 'advanced', label: 'Продвинутый' },
]

/** Место тренировки */
const LOCATION_OPTIONS = [
  { value: 'gym', label: 'Зал' },
  { value: 'home', label: 'Дом' },
  { value: 'outdoor', label: 'Улица' },
]

/** Метки трендов */
const TREND_LABELS: Record<string, { label: string; color: string; icon: string }> = {
  improving: { label: 'Прогресс растёт', color: '#22c55e', icon: '📈' },
  stable: { label: 'Стабильно', color: '#eab308', icon: '➡️' },
  declining: { label: 'Снижение', color: '#ef4444', icon: '📉' },
  insufficient_data: { label: 'Мало данных', color: 'var(--app-hint)', icon: '📊' },
}

export function AICoachPage() {
  const navigate = useNavigate()

  // Активная секция: null | 'build' | 'replace' | 'analyze' | 'recommendations'
  const [activeSection, setActiveSection] = useState<string | null>(null)

  // ── Состояние «Собрать тренировку» ──
  const [selectedMuscles, setSelectedMuscles] = useState<string[]>([])
  const [buildDuration, setBuildDuration] = useState(60)
  const [buildLocation, setBuildLocation] = useState('gym')
  const [buildDifficulty, setBuildDifficulty] = useState('intermediate')
  const [buildNotes, setBuildNotes] = useState('')
  const [buildResult, setBuildResult] = useState<AiBuildWorkoutOut | null>(null)
  const buildWorkout = useAiBuildWorkout()

  // ── Состояние «Заменить упражнение» ──
  const [replaceQuery, setReplaceQuery] = useState('')
  const [replaceExId, setReplaceExId] = useState<number>(0)
  const [replaceExName, setReplaceExName] = useState('')
  const [showReplacePicker, setShowReplacePicker] = useState(false)
  const [replaceResult, setReplaceResult] = useState<AiReplaceExerciseOut | null>(null)
  const { data: replaceExercisesList } = useExerciseSearch(replaceQuery)
  const replaceExercise = useAiReplaceExercise()

  // ── Состояние «Анализ прогресса» ──
  const [analyzeResult, setAnalyzeResult] = useState<AiAnalyzeProgressOut | null>(null)
  const analyzeProgress = useAiAnalyzeProgress()

  // ── Состояние «Рекомендации» ──
  const [recsResult, setRecsResult] = useState<AiRecommendationsOut | null>(null)
  const recommendations = useAiRecommendations()

  // Цель пользователя — для автозаполнения
  const { data: fitnessGoal } = useFitnessGoals()

  // Автозаполнение из цели при первом открытии
  const handleOpenBuild = () => {
    if (fitnessGoal) {
      setBuildLocation(fitnessGoal.training_location || 'gym')
      setBuildDifficulty(fitnessGoal.experience_level || 'intermediate')
    }
    setActiveSection('build')
  }

  // ── Переключение группы мышц ──
  const toggleMuscle = (m: string) => {
    setSelectedMuscles((prev) =>
      prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]
    )
  }

  // ── Обработчики AI-запросов ──

  // Собрать тренировку
  const handleBuildWorkout = async () => {
    if (selectedMuscles.length === 0) return
    const result = await buildWorkout.mutateAsync({
      muscle_groups: selectedMuscles,
      duration_min: buildDuration,
      location: buildLocation,
      difficulty: buildDifficulty,
      notes: buildNotes,
    })
    setBuildResult(result)
  }

  // Заменить упражнение
  const handleReplaceExercise = async () => {
    if (!replaceExId) return
    const result = await replaceExercise.mutateAsync({
      exercise_id: replaceExId,
    })
    setReplaceResult(result)
  }

  // Анализ прогресса
  const handleAnalyzeProgress = async () => {
    const result = await analyzeProgress.mutateAsync()
    setAnalyzeResult(result)
  }

  // Рекомендации
  const handleGetRecommendations = async () => {
    const result = await recommendations.mutateAsync()
    setRecsResult(result)
  }

  // Выбор упражнения для замены
  const handleSelectReplaceEx = (id: number, name: string) => {
    setReplaceExId(id)
    setReplaceExName(name)
    setShowReplacePicker(false)
    setReplaceQuery('')
    setReplaceResult(null)
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-2">
        <button onClick={() => activeSection ? setActiveSection(null) : navigate('/fitness')} className="p-2 -ml-2">
          <ArrowLeft size={22} style={{ color: 'var(--app-text)' }} />
        </button>
        <div className="flex items-center gap-2">
          <Sparkles size={22} style={{ color: '#a5b4fc' }} />
          <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>
            {activeSection ? _sectionTitle(activeSection) : 'AI Coach'}
          </h1>
        </div>
      </div>

      {/* Контент */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
        <AnimatePresence mode="wait">
          {/* ════════════════════════════════════════════════════════════════════
              ГЛАВНОЕ МЕНЮ — 4 действия
              ════════════════════════════════════════════════════════════════════ */}
          {!activeSection && (
            <motion.div
              key="menu"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-3"
            >
              {/* Описание */}
              <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
                AI-ассистент поможет собрать тренировку, подобрать замену упражнению, проанализировать прогресс и дать рекомендации.
              </p>

              {/* Собрать тренировку */}
              <ActionCard
                icon={<Dumbbell size={24} style={{ color: '#818cf8' }} />}
                title="Собрать тренировку"
                desc="AI подберёт упражнения по группам мышц"
                gradient="rgba(99,102,241,0.15)"
                onClick={handleOpenBuild}
              />

              {/* Заменить упражнение */}
              <ActionCard
                icon={<RefreshCw size={24} style={{ color: '#fb923c' }} />}
                title="Заменить упражнение"
                desc="3 альтернативы для любого упражнения"
                gradient="rgba(251,146,60,0.15)"
                onClick={() => setActiveSection('replace')}
              />

              {/* Анализ прогресса */}
              <ActionCard
                icon={<TrendingUp size={24} style={{ color: '#22c55e' }} />}
                title="Анализ прогресса"
                desc="AI объяснит тренды и даст оценку"
                gradient="rgba(34,197,94,0.15)"
                onClick={() => { setActiveSection('analyze'); handleAnalyzeProgress() }}
              />

              {/* Рекомендации */}
              <ActionCard
                icon={<Lightbulb size={24} style={{ color: '#eab308' }} />}
                title="Рекомендации"
                desc="Персональные советы на ближайшую неделю"
                gradient="rgba(234,179,8,0.15)"
                onClick={() => { setActiveSection('recommendations'); handleGetRecommendations() }}
              />
            </motion.div>
          )}

          {/* ════════════════════════════════════════════════════════════════════
              СОБРАТЬ ТРЕНИРОВКУ
              ════════════════════════════════════════════════════════════════════ */}
          {activeSection === 'build' && (
            <motion.div
              key="build"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              {/* Выбор групп мышц */}
              <div>
                <p className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>
                  Группы мышц *
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {MUSCLE_GROUPS.map((mg) => (
                    <button
                      key={mg.value}
                      onClick={() => toggleMuscle(mg.value)}
                      className="flex items-center gap-2 p-3 rounded-xl text-sm font-medium transition-colors"
                      style={{
                        background: selectedMuscles.includes(mg.value)
                          ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                        border: selectedMuscles.includes(mg.value)
                          ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.08)',
                        color: selectedMuscles.includes(mg.value) ? '#a5b4fc' : 'var(--app-text)',
                      }}
                    >
                      <span>{mg.icon}</span>
                      {mg.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Длительность */}
              <div>
                <p className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>
                  Длительность: {buildDuration} мин
                </p>
                <div className="flex gap-2">
                  {[30, 45, 60, 90].map((min) => (
                    <button
                      key={min}
                      onClick={() => setBuildDuration(min)}
                      className="flex-1 py-2 rounded-xl text-sm font-medium"
                      style={{
                        background: buildDuration === min ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                        border: buildDuration === min ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.08)',
                        color: buildDuration === min ? '#a5b4fc' : 'var(--app-text)',
                      }}
                    >
                      {min} мин
                    </button>
                  ))}
                </div>
              </div>

              {/* Уровень + место — в одну строку */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>Уровень</p>
                  <div className="space-y-1.5">
                    {DIFFICULTY_OPTIONS.map((d) => (
                      <button
                        key={d.value}
                        onClick={() => setBuildDifficulty(d.value)}
                        className="w-full py-2 rounded-xl text-xs font-medium"
                        style={{
                          background: buildDifficulty === d.value ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                          border: buildDifficulty === d.value ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.08)',
                          color: buildDifficulty === d.value ? '#a5b4fc' : 'var(--app-text)',
                        }}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>Место</p>
                  <div className="space-y-1.5">
                    {LOCATION_OPTIONS.map((l) => (
                      <button
                        key={l.value}
                        onClick={() => setBuildLocation(l.value)}
                        className="w-full py-2 rounded-xl text-xs font-medium"
                        style={{
                          background: buildLocation === l.value ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                          border: buildLocation === l.value ? '1px solid rgba(99,102,241,0.4)' : '1px solid rgba(255,255,255,0.08)',
                          color: buildLocation === l.value ? '#a5b4fc' : 'var(--app-text)',
                        }}
                      >
                        {l.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Примечания */}
              <textarea
                value={buildNotes}
                onChange={(e) => setBuildNotes(e.target.value)}
                placeholder="Дополнительные пожелания (необязательно)..."
                className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none resize-none"
                style={{ color: 'var(--app-text)', minHeight: '60px' }}
              />

              {/* Кнопка генерации */}
              <button
                onClick={handleBuildWorkout}
                disabled={selectedMuscles.length === 0 || buildWorkout.isPending}
                className="w-full py-4 rounded-2xl text-base font-bold text-white flex items-center justify-center gap-2"
                style={{
                  background: selectedMuscles.length > 0
                    ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                    : 'rgba(255,255,255,0.1)',
                  opacity: buildWorkout.isPending ? 0.6 : 1,
                }}
              >
                {buildWorkout.isPending ? (
                  <><Loader2 size={20} className="animate-spin" /> Генерирую...</>
                ) : (
                  <><Sparkles size={20} /> Собрать тренировку</>
                )}
              </button>

              {/* Результат — собранная тренировка */}
              {buildResult && (
                <GlassCard>
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles size={18} style={{ color: '#a5b4fc' }} />
                    <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                      {buildResult.name}
                    </span>
                  </div>
                  <p className="text-xs mb-3" style={{ color: 'var(--app-hint)' }}>
                    {buildResult.description}
                  </p>
                  <div className="space-y-2">
                    {buildResult.exercises.map((ex, idx) => (
                      <div key={idx} className="flex items-start gap-2 p-2.5 rounded-xl"
                        style={{ background: 'rgba(255,255,255,0.04)' }}>
                        <span className="text-xs font-bold mt-0.5" style={{ color: '#818cf8' }}>
                          {idx + 1}
                        </span>
                        <div className="flex-1">
                          <div className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                            {ex.exercise_name}
                          </div>
                          <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                            {ex.sets}×{ex.reps} · отдых {ex.rest_sec}с
                          </div>
                          {ex.notes && (
                            <div className="text-xs mt-0.5" style={{ color: '#a5b4fc' }}>
                              💡 {ex.notes}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  {/* Кнопка «Начать эту тренировку» */}
                  <button
                    onClick={() => navigate('/fitness/workout')}
                    className="w-full mt-3 py-3 rounded-xl text-sm font-bold text-white"
                    style={{ background: 'linear-gradient(135deg, #22c55e, #16a34a)' }}
                  >
                    ▶ Начать эту тренировку
                  </button>
                </GlassCard>
              )}

              {/* Ошибка */}
              {buildWorkout.isError && (
                <p className="text-sm text-center" style={{ color: '#ef4444' }}>
                  Ошибка генерации. Попробуй ещё раз.
                </p>
              )}
            </motion.div>
          )}

          {/* ════════════════════════════════════════════════════════════════════
              ЗАМЕНИТЬ УПРАЖНЕНИЕ
              ════════════════════════════════════════════════════════════════════ */}
          {activeSection === 'replace' && (
            <motion.div
              key="replace"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
                Выбери упражнение — AI предложит 3 альтернативы с той же группой мышц.
              </p>

              {/* Поиск упражнения */}
              <div className="relative">
                <button
                  onClick={() => setShowReplacePicker(!showReplacePicker)}
                  className="w-full flex items-center justify-between px-3 py-3 rounded-xl border border-white/[0.08] text-sm"
                  style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--app-text)' }}
                >
                  <span>{replaceExName || 'Выбери упражнение...'}</span>
                  <ChevronDown size={16} style={{ color: 'var(--app-hint)' }} />
                </button>

                {/* Выпадающий поиск */}
                {showReplacePicker && (
                  <div
                    className="absolute top-full left-0 right-0 z-10 mt-1 rounded-xl border border-white/[0.08] overflow-hidden"
                    style={{ background: 'var(--glass-bg)', maxHeight: 280 }}
                  >
                    <input
                      type="text"
                      value={replaceQuery}
                      onChange={(e) => setReplaceQuery(e.target.value)}
                      placeholder="Поиск упражнения..."
                      className="w-full px-3 py-2.5 bg-transparent text-sm outline-none border-b border-white/[0.06]"
                      style={{ color: 'var(--app-text)' }}
                      autoFocus
                    />
                    <div className="overflow-y-auto" style={{ maxHeight: 220 }}>
                      {replaceExercisesList?.map((ex) => (
                        <button
                          key={ex.id}
                          onClick={() => handleSelectReplaceEx(ex.id, ex.name)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-white/[0.04]"
                          style={{ color: 'var(--app-text)' }}
                        >
                          {ex.name}
                          <span className="text-xs ml-2" style={{ color: 'var(--app-hint)' }}>
                            {ex.muscle_group}
                          </span>
                        </button>
                      ))}
                      {replaceQuery.length < 2 && (
                        <div className="px-3 py-4 text-xs text-center" style={{ color: 'var(--app-hint)' }}>
                          Введи название (мин. 2 символа)
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Кнопка поиска альтернатив */}
              <button
                onClick={handleReplaceExercise}
                disabled={!replaceExId || replaceExercise.isPending}
                className="w-full py-4 rounded-2xl text-base font-bold text-white flex items-center justify-center gap-2"
                style={{
                  background: replaceExId
                    ? 'linear-gradient(135deg, #fb923c, #ea580c)'
                    : 'rgba(255,255,255,0.1)',
                  opacity: replaceExercise.isPending ? 0.6 : 1,
                }}
              >
                {replaceExercise.isPending ? (
                  <><Loader2 size={20} className="animate-spin" /> Подбираю...</>
                ) : (
                  <><RefreshCw size={20} /> Найти альтернативы</>
                )}
              </button>

              {/* Результат — альтернативы */}
              {replaceResult && (
                <GlassCard>
                  <div className="text-xs font-medium mb-3" style={{ color: 'var(--app-hint)' }}>
                    Замена для «{replaceResult.original}»:
                  </div>
                  <div className="space-y-2">
                    {replaceResult.alternatives.map((alt, idx) => (
                      <div key={idx} className="p-3 rounded-xl" style={{ background: 'rgba(251,146,60,0.08)' }}>
                        <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                          {idx + 1}. {alt.exercise_name}
                        </div>
                        <div className="text-xs mt-1" style={{ color: 'var(--app-hint)' }}>
                          {alt.reason}
                        </div>
                      </div>
                    ))}
                  </div>
                </GlassCard>
              )}

              {/* Ошибка */}
              {replaceExercise.isError && (
                <p className="text-sm text-center" style={{ color: '#ef4444' }}>
                  Ошибка подбора. Попробуй ещё раз.
                </p>
              )}
            </motion.div>
          )}

          {/* ════════════════════════════════════════════════════════════════════
              АНАЛИЗ ПРОГРЕССА
              ════════════════════════════════════════════════════════════════════ */}
          {activeSection === 'analyze' && (
            <motion.div
              key="analyze"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              {/* Загрузка */}
              {analyzeProgress.isPending && (
                <div className="flex flex-col items-center justify-center py-12">
                  <Loader2 size={36} className="animate-spin mb-4" style={{ color: '#22c55e' }} />
                  <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
                    Анализирую данные...
                  </p>
                </div>
              )}

              {/* Результат */}
              {analyzeResult && (
                <>
                  {/* Тренд */}
                  {analyzeResult.trend && TREND_LABELS[analyzeResult.trend] && (
                    <GlassCard className="flex items-center gap-3">
                      <span className="text-2xl">{TREND_LABELS[analyzeResult.trend].icon}</span>
                      <div>
                        <div className="text-sm font-bold" style={{ color: TREND_LABELS[analyzeResult.trend].color }}>
                          {TREND_LABELS[analyzeResult.trend].label}
                        </div>
                        <div className="text-xs" style={{ color: 'var(--app-hint)' }}>Общий тренд</div>
                      </div>
                    </GlassCard>
                  )}

                  {/* Текстовый анализ */}
                  <GlassCard>
                    <div className="flex items-center gap-2 mb-2">
                      <TrendingUp size={16} style={{ color: '#22c55e' }} />
                      <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                        Анализ
                      </span>
                    </div>
                    <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>
                      {analyzeResult.analysis}
                    </p>
                  </GlassCard>

                  {/* Ключевые наблюдения */}
                  {analyzeResult.highlights.length > 0 && (
                    <GlassCard>
                      <div className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>
                        Ключевые наблюдения
                      </div>
                      <div className="space-y-2">
                        {analyzeResult.highlights.map((h, idx) => (
                          <div key={idx} className="flex items-start gap-2">
                            <span className="text-xs mt-0.5" style={{ color: '#22c55e' }}>•</span>
                            <span className="text-sm" style={{ color: 'var(--app-text)' }}>{h}</span>
                          </div>
                        ))}
                      </div>
                    </GlassCard>
                  )}

                  {/* Кнопка повторного анализа */}
                  <button
                    onClick={handleAnalyzeProgress}
                    disabled={analyzeProgress.isPending}
                    className="w-full py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2"
                    style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}
                  >
                    <RefreshCw size={16} /> Обновить анализ
                  </button>
                </>
              )}

              {/* Ошибка */}
              {analyzeProgress.isError && (
                <div className="flex flex-col items-center py-8">
                  <p className="text-sm mb-3" style={{ color: '#ef4444' }}>
                    Ошибка анализа. Попробуй ещё раз.
                  </p>
                  <button
                    onClick={handleAnalyzeProgress}
                    className="px-6 py-2 rounded-xl text-sm font-medium"
                    style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}
                  >
                    Повторить
                  </button>
                </div>
              )}
            </motion.div>
          )}

          {/* ════════════════════════════════════════════════════════════════════
              РЕКОМЕНДАЦИИ
              ════════════════════════════════════════════════════════════════════ */}
          {activeSection === 'recommendations' && (
            <motion.div
              key="recs"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="space-y-4"
            >
              {/* Загрузка */}
              {recommendations.isPending && (
                <div className="flex flex-col items-center justify-center py-12">
                  <Loader2 size={36} className="animate-spin mb-4" style={{ color: '#eab308' }} />
                  <p className="text-sm" style={{ color: 'var(--app-hint)' }}>
                    Формирую рекомендации...
                  </p>
                </div>
              )}

              {/* Результат */}
              {recsResult && (
                <>
                  {/* Фокус на неделю */}
                  {recsResult.weekly_focus && (
                    <GlassCard className="flex items-center gap-3">
                      <span className="text-2xl">🎯</span>
                      <div>
                        <div className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                          Фокус на неделю
                        </div>
                        <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                          {recsResult.weekly_focus}
                        </div>
                      </div>
                    </GlassCard>
                  )}

                  {/* Список рекомендаций */}
                  <div className="space-y-2">
                    {recsResult.recommendations.map((rec, idx) => (
                      <GlassCard key={idx}>
                        <div className="flex items-start gap-3">
                          <span className="text-xl">{rec.icon}</span>
                          <div>
                            <div className="text-sm font-bold mb-1" style={{ color: 'var(--app-text)' }}>
                              {rec.title}
                            </div>
                            <div className="text-xs leading-relaxed" style={{ color: 'var(--app-hint)' }}>
                              {rec.text}
                            </div>
                          </div>
                        </div>
                      </GlassCard>
                    ))}
                  </div>

                  {/* Кнопка обновления */}
                  <button
                    onClick={handleGetRecommendations}
                    disabled={recommendations.isPending}
                    className="w-full py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2"
                    style={{ background: 'rgba(234,179,8,0.15)', color: '#eab308' }}
                  >
                    <RefreshCw size={16} /> Обновить рекомендации
                  </button>
                </>
              )}

              {/* Ошибка */}
              {recommendations.isError && (
                <div className="flex flex-col items-center py-8">
                  <p className="text-sm mb-3" style={{ color: '#ef4444' }}>
                    Ошибка. Попробуй ещё раз.
                  </p>
                  <button
                    onClick={handleGetRecommendations}
                    className="px-6 py-2 rounded-xl text-sm font-medium"
                    style={{ background: 'rgba(234,179,8,0.15)', color: '#eab308' }}
                  >
                    Повторить
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}

/** Карточка действия на главном экране AI Coach */
function ActionCard({
  icon, title, desc, gradient, onClick,
}: {
  icon: React.ReactNode
  title: string
  desc: string
  gradient: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-4 p-4 rounded-2xl text-left border border-white/[0.08] transition-transform active:scale-[0.98]"
      style={{ background: gradient }}
    >
      <div className="w-12 h-12 rounded-2xl flex items-center justify-center"
        style={{ background: 'rgba(255,255,255,0.08)' }}>
        {icon}
      </div>
      <div className="flex-1">
        <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>{title}</div>
        <div className="text-xs" style={{ color: 'var(--app-hint)' }}>{desc}</div>
      </div>
    </button>
  )
}

/** Заголовок секции */
function _sectionTitle(section: string): string {
  switch (section) {
    case 'build': return 'Собрать тренировку'
    case 'replace': return 'Замена упражнения'
    case 'analyze': return 'Анализ прогресса'
    case 'recommendations': return 'Рекомендации'
    default: return 'AI Coach'
  }
}
