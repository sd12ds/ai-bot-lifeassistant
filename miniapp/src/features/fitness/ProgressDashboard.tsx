/**
 * Дашборд прогресса с графиками (recharts).
 * Вес тела (линейный), объём по неделям (столбцы + overlay линия sessions/week),
 * активности по неделям, прогресс по упражнению (dropdown), рекорды, streak.
 */
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Trophy, Sparkles, Loader2, ChevronDown } from 'lucide-react'
import {
  ResponsiveContainer, LineChart, Line, Bar, ComposedChart,
  XAxis, YAxis, CartesianGrid, Tooltip, Area, AreaChart,
} from 'recharts'
import {
  useBodyMetrics, useWeeklyVolume, useExerciseProgress,
  useFitnessStats, useRecords, useAiAnalyzeProgress,
  useWeeklyActivities, useActivities,
  ACTIVITY_LABELS, ACTIVITY_EMOJI,
  type AiAnalyzeProgressOut,
} from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'

/** Кастомный тултип для графиков */
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div
      className="px-3 py-2 rounded-xl text-xs"
      style={{ background: 'rgba(0,0,0,0.85)', border: '1px solid rgba(255,255,255,0.1)' }}
    >
      <div style={{ color: 'var(--app-hint)' }}>{label}</div>
      {payload.map((p: any, i: number) => (
        <div key={i} className="font-bold" style={{ color: p.color }}>
          {typeof p.value === 'number' ? Math.round(p.value * 10) / 10 : p.value}{' '}
          {p.dataKey === 'volume' ? 'кг' : p.dataKey === 'sessions' ? 'тр.' : p.dataKey === 'weight' ? 'кг' : p.dataKey === 'time_min' ? 'мин' : p.dataKey === 'metric' ? '' : p.dataKey === 'count' ? 'акт.' : ''}
        </div>
      ))}
    </div>
  )
}

export function ProgressDashboard() {
  const navigate = useNavigate()

  // Данные для графиков
  const { data: bodyMetrics } = useBodyMetrics(90)
  const { data: weeklyVolume } = useWeeklyVolume(12)
  // Фильтр активностей по типу
  const [activityFilter, setActivityFilter] = useState<string>('')
  const [actDropdownOpen, setActDropdownOpen] = useState(false)
  const actDropdownRef = useRef<HTMLDivElement>(null)
  const { data: weeklyActivities } = useWeeklyActivities(12, activityFilter || undefined)
  const { data: rawActivities } = useActivities(90) // для получения уникальных типов
  const { data: stats } = useFitnessStats(90)
  const { data: records } = useRecords()

  // Прогресс по конкретному упражнению
  const [selectedExId, setSelectedExId] = useState<number>(0)
  const [selectedExName, setSelectedExName] = useState('')
  // Кастомный dropdown — состояние открытия
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // Автоматически выбираем первое упражнение из топа при загрузке данных
  useEffect(() => {
    if (selectedExId === 0 && stats?.top_exercises?.length) {
      const first = stats.top_exercises[0]
      setSelectedExId(first.exercise_id)
      setSelectedExName(first.name)
    }
  }, [stats])

  // Закрытие dropdown при клике вне
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
      }
    }
    if (dropdownOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [dropdownOpen])

  // Закрытие dropdown активностей при клике вне
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (actDropdownRef.current && !actDropdownRef.current.contains(e.target as Node)) {
        setActDropdownOpen(false)
      }
    }
    if (actDropdownOpen) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [actDropdownOpen])

  // Уникальные типы активностей пользователя
  const activityTypes = Array.from(new Set((rawActivities || []).map(a => a.activity_type)))

  // AI анализ прогресса
  const [aiAnalysis, setAiAnalysis] = useState<AiAnalyzeProgressOut | null>(null)
  const analyzeProgress = useAiAnalyzeProgress()

  // Обработчик запроса AI анализа
  const handleAiAnalysis = async () => {
    try {
      const result = await analyzeProgress.mutateAsync()
      setAiAnalysis(result)
    } catch (e) {
      console.error('Ошибка AI анализа:', e)
    }
  }
  const { data: exerciseProgress } = useExerciseProgress(selectedExId)

  // Подготовка данных — вес тела
  const weightData = (bodyMetrics || [])
    .filter((m) => m.weight_kg)
    .map((m) => ({
      date: m.logged_at ? new Date(m.logged_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '',
      weight: m.weight_kg,
    }))
    .reverse() // хронологический порядок

  // Подготовка данных — объём по неделям + количество тренировок
  const volumeData = (weeklyVolume || []).map((w) => ({
    week: w.week.slice(5, 10), // ММ-ДД из даты
    volume: Math.round(w.volume),
    sessions: w.sessions, // Количество тренировок — для overlay линии
    duration: Math.round(w.duration_min),
  }))

  // Определяем единицу измерения для отфильтрованного типа
  const filteredUnit = activityFilter
    ? (rawActivities || []).find(a => a.activity_type === activityFilter)?.unit || 'min'
    : 'min'
  // Подбираем label и ключ данных в зависимости от единицы
  const UNIT_LABELS: Record<string, string> = { km: 'км', min: 'мин', steps: 'шагов', m: 'м' }
  const metricLabel = activityFilter ? (UNIT_LABELS[filteredUnit] || filteredUnit) : 'мин'
  // Если фильтр активен — показываем value_sum (оригинальная метрика), иначе time_min
  const useValueSum = activityFilter && filteredUnit !== 'min'

  // Подготовка данных — активности по неделям
  const activityData = (weeklyActivities || []).map((w) => ({
    week: w.week.slice(5, 10), // ММ-ДД
    metric: useValueSum ? Math.round(w.value_sum * 10) / 10 : Math.round(w.time_min),
    count: w.count,
    calories: Math.round(w.calories),
  }))

  // Подготовка данных — прогресс по упражнению
  const exProgressData = (exerciseProgress || []).map((p) => ({
    date: new Date(p.date).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
    weight: p.max_weight,
    volume: Math.round(p.volume),
    reps: p.max_reps,
  }))

  // Выбор упражнения через dropdown
  const handleExSelect = (id: number, name: string) => {
    setSelectedExId(id)
    setSelectedExName(name)
    setDropdownOpen(false)
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-2">
        <button onClick={() => navigate('/fitness')} className="p-2 -ml-2">
          <ArrowLeft size={22} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>
          Прогресс
        </h1>
      </div>

      {/* Контент */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
        {/* ── Streak + общая статистика ── */}
        {stats && (
          <GlassCard className="flex items-center gap-4">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
              style={{
                background: stats.current_streak_days > 0
                  ? 'linear-gradient(135deg, rgba(251,146,60,0.3), rgba(234,88,12,0.2))'
                  : 'rgba(255,255,255,0.06)',
              }}
            >
              {stats.current_streak_days > 0 ? '🔥' : '💤'}
            </div>
            <div className="flex-1">
              <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
                {stats.current_streak_days}
              </div>
              <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                дней подряд
              </div>
            </div>
            {/* Мини-статы: тренировки + активности */}
            <div className="text-right text-xs" style={{ color: 'var(--app-hint)' }}>
              <div>
                <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  {stats.total_sessions}
                </span>{' '}тренировок
              </div>
              {stats.total_activities > 0 && (
                <div>
                  <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                    {stats.total_activities}
                  </span>{' '}активностей
                </div>
              )}
              <div>
                <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  {Math.round(stats.total_time_min + (stats.total_activity_time_min || 0))}
                </span>{' '}мин
              </div>
            </div>
          </GlassCard>
        )}

        {/* ── График веса тела ── */}
        {weightData.length > 1 && (
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                ⚖️ Вес тела
              </span>
              <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
                {weightData.length} замеров
              </span>
            </div>
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={weightData}>
                  <defs>
                    <linearGradient id="weightGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    domain={['auto', 'auto']}
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={35}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="weight"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fill="url(#weightGrad)"
                    dot={{ r: 3, fill: '#6366f1' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        )}

        {/* ── Объём по неделям (столбцы) + overlay линия sessions/week ── */}
        {volumeData.length > 0 && (
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                📊 Объём и тренировки
              </span>
              <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
                последние {volumeData.length} нед
              </span>
            </div>
            {/* Легенда */}
            <div className="flex gap-4 mb-2 text-[10px]" style={{ color: 'var(--app-hint)' }}>
              <div className="flex items-center gap-1">
                <div className="w-3 h-2 rounded-sm" style={{ background: '#8b5cf6' }} />
                Объём (кг)
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-0.5 rounded-sm" style={{ background: '#22c55e' }} />
                Тренировок
              </div>
            </div>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                {/* ComposedChart — столбцы объёма + линия тренировок */}
                <ComposedChart data={volumeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis
                    dataKey="week"
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  {/* Левая ось — объём */}
                  <YAxis
                    yAxisId="volume"
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  {/* Правая ось — количество тренировок */}
                  <YAxis
                    yAxisId="sessions"
                    orientation="right"
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={25}
                    domain={[0, 'auto']}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  {/* Столбцы объёма */}
                  <Bar
                    yAxisId="volume"
                    dataKey="volume"
                    fill="#8b5cf6"
                    radius={[6, 6, 0, 0]}
                    maxBarSize={32}
                  />
                  {/* Overlay линия — количество тренировок в неделю */}
                  <Line
                    yAxisId="sessions"
                    type="monotone"
                    dataKey="sessions"
                    stroke="#22c55e"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#22c55e' }}
                    name="Тренировок"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        )}

        {/* ── Активности по неделям (кардио, растяжка и пр.) ── */}
        {(activityData.length > 0 || activityFilter) && (
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                🏃 Активности по неделям
              </span>

              {/* Dropdown фильтр по типу активности */}
              {activityTypes.length > 0 && (
                <div className="relative" ref={actDropdownRef}>
                  <button
                    onClick={() => setActDropdownOpen(!actDropdownOpen)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                    style={{
                      background: 'rgba(245,158,11,0.15)',
                      color: '#f59e0b',
                      border: '1px solid rgba(245,158,11,0.25)',
                    }}
                  >
                    {activityFilter
                      ? `${ACTIVITY_EMOJI[activityFilter] || '🏃'} ${ACTIVITY_LABELS[activityFilter] || activityFilter}`
                      : 'Все'}
                    <ChevronDown
                      size={14}
                      className={`transition-transform ${actDropdownOpen ? 'rotate-180' : ''}`}
                    />
                  </button>
                  {actDropdownOpen && (
                    <div
                      className="absolute right-0 top-full mt-1 rounded-xl py-1 z-50 min-w-[180px] max-h-[240px] overflow-y-auto"
                      style={{
                        background: 'rgba(20,20,30,0.95)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        backdropFilter: 'blur(20px)',
                      }}
                    >
                      {/* Опция «Все» */}
                      <button
                        onClick={() => { setActivityFilter(''); setActDropdownOpen(false) }}
                        className="w-full text-left px-4 py-2.5 text-xs transition-colors"
                        style={{
                          color: !activityFilter ? '#f59e0b' : 'var(--app-text)',
                          background: !activityFilter ? 'rgba(245,158,11,0.1)' : 'transparent',
                        }}
                      >
                        🏃 Все активности
                      </button>
                      {activityTypes.map((t) => (
                        <button
                          key={t}
                          onClick={() => { setActivityFilter(t); setActDropdownOpen(false) }}
                          className="w-full text-left px-4 py-2.5 text-xs transition-colors"
                          style={{
                            color: activityFilter === t ? '#f59e0b' : 'var(--app-text)',
                            background: activityFilter === t ? 'rgba(245,158,11,0.1)' : 'transparent',
                          }}
                        >
                          {ACTIVITY_EMOJI[t] || '🏃'} {ACTIVITY_LABELS[t] || t}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            {/* Легенда */}
            <div className="flex gap-4 mb-2 text-[10px]" style={{ color: 'var(--app-hint)' }}>
              <div className="flex items-center gap-1">
                <div className="w-3 h-2 rounded-sm" style={{ background: '#f59e0b' }} />
                {activityFilter && filteredUnit !== 'min'
                  ? `Значение (${metricLabel})`
                  : 'Время (мин)'}
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-0.5 rounded-sm" style={{ background: '#06b6d4' }} />
                Активностей
              </div>
            </div>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={activityData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis
                    dataKey="week"
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  {/* Левая ось — время в минутах */}
                  <YAxis
                    yAxisId="time"
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={35}
                    tickFormatter={(v) => `${v}`}
                  />
                  {/* Правая ось — количество активностей */}
                  <YAxis
                    yAxisId="count"
                    orientation="right"
                    tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                    axisLine={false}
                    tickLine={false}
                    width={25}
                    domain={[0, 'auto']}
                  />
                  <Tooltip content={<ChartTooltip />} />
                  {/* Столбцы — время */}
                  <Bar
                    yAxisId="time"
                    dataKey="metric"
                    fill="#f59e0b"
                    radius={[6, 6, 0, 0]}
                    maxBarSize={32}
                    name={activityFilter && filteredUnit !== 'min' ? metricLabel : 'Время (мин)'}
                  />
                  {/* Overlay линия — количество */}
                  <Line
                    yAxisId="count"
                    type="monotone"
                    dataKey="count"
                    stroke="#06b6d4"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#06b6d4' }}
                    name="Активностей"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        )}

        {/* ── Прогресс по упражнению (кастомный dropdown) ── */}
        {stats?.top_exercises && stats.top_exercises.length > 0 && (
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                🏋️ Рабочий вес
              </span>

              {/* Кастомный dropdown выбора упражнения */}
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all"
                  style={{
                    background: 'rgba(34,197,94,0.15)',
                    color: '#22c55e',
                    border: '1px solid rgba(34,197,94,0.25)',
                  }}
                >
                  {selectedExName || 'Упражнение'}
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${dropdownOpen ? 'rotate-180' : ''}`}
                  />
                </button>

                {/* Выпадающее меню */}
                {dropdownOpen && (
                  <div
                    className="absolute right-0 top-full mt-1 rounded-xl py-1 z-50 min-w-[200px] max-h-[240px] overflow-y-auto"
                    style={{
                      background: 'rgba(20,20,30,0.95)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      backdropFilter: 'blur(20px)',
                    }}
                  >
                    {stats.top_exercises.map((ex) => (
                      <button
                        key={ex.exercise_id}
                        onClick={() => handleExSelect(ex.exercise_id, ex.name)}
                        className="w-full text-left px-4 py-2.5 text-xs transition-colors flex items-center justify-between"
                        style={{
                          color: selectedExId === ex.exercise_id ? '#22c55e' : 'var(--app-text)',
                          background: selectedExId === ex.exercise_id ? 'rgba(34,197,94,0.1)' : 'transparent',
                        }}
                      >
                        <span>{ex.name}</span>
                        <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                          {ex.sets_count} подх
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* График прогресса выбранного упражнения */}
            {exProgressData.length > 1 ? (
              <>
                <div className="h-[180px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={exProgressData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        width={35}
                        tickFormatter={(v) => `${v}кг`}
                      />
                      <Tooltip content={<ChartTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="weight"
                        stroke="#22c55e"
                        strokeWidth={2.5}
                        dot={{ r: 4, fill: '#22c55e', strokeWidth: 0 }}
                        activeDot={{ r: 6 }}
                        name="Макс вес"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                {/* Последнее значение + динамика */}
                {exProgressData.length >= 2 && (() => {
                  const last = exProgressData[exProgressData.length - 1]
                  const prev = exProgressData[exProgressData.length - 2]
                  const diff = last.weight && prev.weight
                    ? Math.round((last.weight - prev.weight) * 10) / 10
                    : null
                  return (
                    <div className="flex items-center justify-between mt-2 px-1">
                      <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
                        Текущий макс
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                          {last.weight} кг
                        </span>
                        {diff !== null && diff !== 0 && (
                          <span className="text-xs font-medium"
                            style={{ color: diff > 0 ? '#22c55e' : '#f87171' }}>
                            {diff > 0 ? '+' : ''}{diff} кг
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })()}
              </>
            ) : (
              <div className="py-5 text-center text-sm" style={{ color: 'var(--app-hint)' }}>
                Недостаточно данных — тренируйся больше 🏋️
              </div>
            )}
          </GlassCard>
        )}

        {/* ── AI анализ прогресса ── */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Sparkles size={18} style={{ color: '#a5b4fc' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                AI анализ
              </span>
            </div>
            <button
              onClick={handleAiAnalysis}
              disabled={analyzeProgress.isPending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium"
              style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}
            >
              {analyzeProgress.isPending ? (
                <><Loader2 size={12} className="animate-spin" /> Анализ...</>
              ) : (
                <><Sparkles size={12} /> Анализировать</>
              )}
            </button>
          </div>
          {/* Результат AI анализа */}
          {aiAnalysis && (
            <div className="space-y-2">
              <p className="text-sm leading-relaxed" style={{ color: 'var(--app-text)' }}>
                {aiAnalysis.analysis}
              </p>
              {aiAnalysis.highlights.length > 0 && (
                <div className="pt-2 border-t border-white/[0.06] space-y-1">
                  {aiAnalysis.highlights.map((h, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-xs">
                      <span style={{ color: '#22c55e' }}>•</span>
                      <span style={{ color: 'var(--app-hint)' }}>{h}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
          {/* Ошибка */}
          {analyzeProgress.isError && (
            <p className="text-xs" style={{ color: '#ef4444' }}>
              Ошибка анализа. Попробуй ещё раз.
            </p>
          )}
          {/* Пустое состояние */}
          {!aiAnalysis && !analyzeProgress.isPending && !analyzeProgress.isError && (
            <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
              Нажми «Анализировать» — AI изучит твои данные и даст оценку
            </p>
          )}
        </GlassCard>

        {/* ── Личные рекорды ── */}
        {records && records.length > 0 && (
          <GlassCard>
            <div className="flex items-center gap-2 mb-3">
              <Trophy size={18} style={{ color: '#eab308' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                Личные рекорды
              </span>
            </div>
            <div className="space-y-2">
              {records.slice(0, 10).map((rec, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-2.5 rounded-xl"
                  style={{ background: 'rgba(234,179,8,0.06)' }}
                >
                  <div>
                    <div className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                      {rec.exercise}
                    </div>
                    <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                      {rec.record_type === 'max_weight' ? 'Максимальный вес' : rec.record_type}
                      {rec.achieved_at && ` · ${new Date(rec.achieved_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}`}
                    </div>
                  </div>
                  <span className="text-sm font-bold" style={{ color: '#eab308' }}>
                    {rec.value} {rec.record_type === 'max_weight' ? 'кг' : ''}
                  </span>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        {/* Пустое состояние — учитываем и тренировки, и активности */}
        {!stats?.total_sessions && !stats?.total_activities && weightData.length === 0 && (
          <div className="flex flex-col items-center justify-center py-8">
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center mb-4 text-3xl"
              style={{ background: 'rgba(99,102,241,0.1)' }}
            >
              📊
            </div>
            <p className="text-base font-bold mb-1" style={{ color: 'var(--app-text)' }}>
              Пока нет данных
            </p>
            <p className="text-sm text-center px-8" style={{ color: 'var(--app-hint)' }}>
              Записывай тренировки и замеры, чтобы отслеживать прогресс
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
