/**
 * Главная страница фитнес-модуля — дашборд.
 * Streak, карточка "Сегодня", недельная активность с прогрессом, быстрые действия, последние тренировки, статистика.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, ChevronRight, Plus, History, Play, BarChart3, Ruler, Target, Sparkles } from 'lucide-react'
import { useFitnessStats, useSessions, useBodyMetrics, useNextWorkout, useFitnessGoals, type WorkoutSession } from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'
import { FAB } from '../../shared/components/FAB'
import { QuickWorkoutSheet } from './QuickWorkoutSheet'

/** Дни недели */
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

/** Типы тренировок */
const WORKOUT_TYPE_LABELS: Record<string, { label: string; icon: string }> = {
  strength: { label: 'Силовая', icon: '🏋️' },
  cardio: { label: 'Кардио', icon: '🏃' },
  home: { label: 'Домашняя', icon: '🏠' },
  functional: { label: 'Функциональная', icon: '⚡' },
  stretching: { label: 'Растяжка', icon: '🧘' },
}

export function FitnessPage() {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  // Данные
  const { data: stats } = useFitnessStats(30)
  const { data: recentSessions } = useSessions(7)
  const { data: bodyMetrics } = useBodyMetrics(30)
  // Следующая тренировка из активной программы
  const { data: nextWorkout } = useNextWorkout()
  // Цель тренировок в неделю
  const { data: fitnessGoal } = useFitnessGoals()

  // Определяем дни тренировок за текущую неделю
  const weekWorkoutDays = getWeekWorkoutDays(recentSessions || [])
  // Количество тренировок на этой неделе
  const weekWorkoutCount = weekWorkoutDays.size

  // Последний вес
  const lastWeight = bodyMetrics?.[0]?.weight_kg

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>
            Фитнес
          </h1>
          <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
            {new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
          </p>
        </div>
        <button
          onClick={() => navigate('/fitness/history')}
          className="p-2 rounded-xl"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <History size={20} style={{ color: 'var(--app-hint)' }} />
        </button>
      </div>

      {/* Контент */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
        {/* ── Streak-виджет ── */}
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
                {stats.current_streak_days > 0 ? 'дней подряд' : 'Начни серию тренировок!'}
              </div>
            </div>
            {/* Мини-статы */}
            <div className="text-right text-xs" style={{ color: 'var(--app-hint)' }}>
              <div>
                <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  {stats.total_sessions}
                </span>{' '}
                за 30 дн
              </div>
              {stats.total_volume_kg > 0 && (
                <div>
                  <span className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                    {Math.round(stats.total_volume_kg)}
                  </span>{' '}
                  кг
                </div>
              )}
            </div>
          </GlassCard>
        )}

        {/* ── Карточка «Сегодня» — следующая тренировка из программы ── */}
        {nextWorkout && (
          <GlassCard
            className="cursor-pointer"
            onClick={() => navigate('/fitness/workout')}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-12 h-12 rounded-2xl flex items-center justify-center text-xl"
                style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.25), rgba(139,92,246,0.15))' }}
              >
                📋
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-xs font-medium mb-0.5" style={{ color: '#a5b4fc' }}>
                  {nextWorkout.is_today
                    ? 'Сегодня по программе'
                    : `Следующая${nextWorkout.weekday_name ? ` · ${nextWorkout.weekday_name}` : ''}`}
                </div>
                <div className="text-sm font-bold truncate" style={{ color: 'var(--app-text)' }}>
                  {nextWorkout.day_name || `День ${nextWorkout.day_number}`}
                </div>
                <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                  {nextWorkout.program_name} · {nextWorkout.completed_workouts}/{nextWorkout.total_days} дней
                </div>
              </div>
              <ChevronRight size={18} style={{ color: 'var(--app-hint)' }} />
            </div>
          </GlassCard>
        )}

        {/* ── Недельная активность + прогресс ── */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
              Эта неделя
            </span>
            {/* Прогресс: X/7 тренировок */}
            <span className="text-xs font-medium" style={{ color: weekWorkoutCount > 0 ? '#a5b4fc' : 'var(--app-hint)' }}>
              {weekWorkoutCount}/{fitnessGoal?.workouts_per_week || 7} тренировок
            </span>
          </div>
          <div className="flex justify-between">
            {WEEKDAYS.map((day, idx) => {
              const hasWorkout = weekWorkoutDays.has(idx)
              return (
                <div key={day} className="flex flex-col items-center gap-1.5">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium"
                    style={{
                      background: hasWorkout
                        ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                        : 'rgba(255,255,255,0.06)',
                      color: hasWorkout ? 'white' : 'var(--app-hint)',
                    }}
                  >
                    {hasWorkout ? '✓' : ''}
                  </div>
                  <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    {day}
                  </span>
                </div>
              )
            })}
          </div>
        </GlassCard>

        {/* ── Быстрые действия ── */}
        <div className="grid grid-cols-3 gap-3">
          {/* Начать тренировку */}
          <button
            onClick={() => navigate('/fitness/workout')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.15), rgba(16,185,129,0.1))' }}
          >
            <Play size={20} style={{ color: '#22c55e' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Начать
            </span>
          </button>
          {/* Записать тренировку — быстрый лог */}
          <button
            onClick={() => setCreateOpen(true)}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1))' }}
          >
            <Plus size={20} style={{ color: '#818cf8' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Записать
            </span>
          </button>
          {/* Прогресс */}
          <button
            onClick={() => navigate('/fitness/progress')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            <BarChart3 size={20} style={{ color: '#a78bfa' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Прогресс
            </span>
          </button>
          {/* История */}
          <button
            onClick={() => navigate('/fitness/history')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'rgba(255,255,255,0.04)' }}
          >
            <History size={20} style={{ color: 'var(--app-hint)' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              История
            </span>
          </button>
          {/* Программы */}
          <button
            onClick={() => navigate('/fitness/programs')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(251,146,60,0.15), rgba(234,88,12,0.1))' }}
          >
            <Target size={20} style={{ color: '#fb923c' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Программы
            </span>
          </button>
          {/* Замеры */}
          <button
            onClick={() => navigate('/fitness/body')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.15), rgba(16,185,129,0.1))' }}
          >
            <Ruler size={20} style={{ color: '#22c55e' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              Замеры
            </span>
          </button>
          {/* AI Coach */}
          <button
            onClick={() => navigate('/fitness/coach')}
            className="flex items-center gap-3 p-4 rounded-2xl border border-white/[0.08]"
            style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.15))' }}
          >
            <Sparkles size={20} style={{ color: '#a5b4fc' }} />
            <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
              AI Coach
            </span>
          </button>
        </div>

        {/* ── Статистика за 30 дней ── */}
        {stats && stats.total_sessions > 0 && (
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                За 30 дней
              </span>
              <TrendingUp size={16} style={{ color: '#818cf8' }} />
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                  {stats.total_sessions}
                </div>
                <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                  тренировок
                </div>
              </div>
              <div>
                <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                  {stats.total_time_min > 0 ? Math.round(stats.total_time_min) : '—'}
                </div>
                <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                  минут
                </div>
              </div>
              <div>
                <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                  {stats.total_volume_kg > 0 ? `${Math.round(stats.total_volume_kg / 1000)}т` : '—'}
                </div>
                <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                  объём
                </div>
              </div>
            </div>

            {/* Топ упражнений */}
            {stats.top_exercises.length > 0 && (
              <div className="mt-3 pt-3 border-t border-white/[0.06]">
                <div className="text-[10px] font-medium mb-2" style={{ color: 'var(--app-hint)' }}>
                  Топ упражнений
                </div>
                <div className="space-y-1.5">
                  {stats.top_exercises.slice(0, 3).map((ex, i) => (
                    <div key={ex.exercise_id} className="flex items-center justify-between text-xs">
                      <span style={{ color: 'var(--app-text)' }}>
                        {i + 1}. {ex.name}
                      </span>
                      <span style={{ color: 'var(--app-hint)' }}>{ex.sets_count} подх</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </GlassCard>
        )}

        {/* ── Последние тренировки (детальные карточки) ── */}
        {(() => {
          // Фильтруем пустые сессии (0 подходов и <30 сек)
          const filtered = recentSessions?.filter(s => {
            const hasSets = (s.sets?.length || 0) > 0
            const hasVolume = (s.total_volume_kg || 0) > 0
            const hasRealDuration = (s.total_duration_sec || 0) >= 30
            return hasSets || hasVolume || hasRealDuration
          })
          if (!filtered || filtered.length === 0) return null
          return (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                  Последние тренировки
                </span>
                <button onClick={() => navigate('/fitness/history')}
                  className="flex items-center gap-0.5 text-xs"
                  style={{ color: '#818cf8' }}>
                  Все <ChevronRight size={14} />
                </button>
              </div>
              <div className="space-y-2">
                {filtered.slice(0, 3).map((s) => {
                  const type = WORKOUT_TYPE_LABELS[s.workout_type] || { label: s.workout_type, icon: '🏋️' }
                  const dateStr = s.started_at
                    ? new Date(s.started_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', weekday: 'short' })
                    : ''
                  const startTime = s.started_at
                    ? new Date(s.started_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
                    : ''
                  const endTime = s.ended_at
                    ? new Date(s.ended_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
                    : ''
                  const timeRange = startTime && endTime && startTime !== endTime
                    ? `${startTime}–${endTime}` : ''
                  const durMin = s.total_duration_sec ? Math.round(s.total_duration_sec / 60) : 0
                  const durStr = durMin >= 60
                    ? `${Math.floor(durMin / 60)}ч ${durMin % 60}мин`
                    : durMin > 0 ? `${durMin} мин` : ''
                  // Группировка упражнений
                  const exMap = new Map<number, { name: string; cnt: number; weight: number }>()
                  s.sets?.forEach((st) => {
                    if (!exMap.has(st.exercise_id)) {
                      exMap.set(st.exercise_id, {
                        name: st.exercise_name || `#${st.exercise_id}`,
                        cnt: 0, weight: 0,
                      })
                    }
                    const ex = exMap.get(st.exercise_id)!
                    ex.cnt++
                    if (st.weight_kg && st.weight_kg > ex.weight) ex.weight = st.weight_kg
                  })
                  const exercises = Array.from(exMap.values())
                  // По программе или свободная
                  const isProgram = s.name && !s.name.startsWith('Тренировка ')
                  const badgeColor = isProgram ? '#fb923c' : '#818cf8'
                  const badgeText = isProgram ? 'Программа' : 'Свободная'

                  return (
                    <GlassCard key={s.id} className="!p-3">
                      {/* Заголовок */}
                      <div className="flex items-start gap-2 mb-1.5">
                        <span className="text-lg">{type.icon}</span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                            {s.name || type.label}
                          </div>
                          <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold"
                              style={{ background: `${badgeColor}22`, color: badgeColor }}>
                              {badgeText}
                            </span>
                            <span className="text-[11px]" style={{ color: 'var(--app-hint)' }}>
                              {dateStr}
                              {timeRange ? ` · ${timeRange}` : ''}
                              {durStr ? ` · ${durStr}` : ''}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Упражнения (до 3шт) */}
                      {exercises.length > 0 && (
                        <div className="space-y-0.5">
                          {exercises.slice(0, 3).map((ex, idx) => (
                            <div key={idx} className="flex items-center justify-between text-[11px]">
                              <span className="truncate" style={{ color: 'var(--app-text)', maxWidth: '60%' }}>
                                {ex.name}
                              </span>
                              <span style={{ color: 'var(--app-hint)', fontSize: 10 }}>
                                {ex.cnt} подх{ex.weight > 0 ? ` · ${ex.weight} кг` : ''}
                              </span>
                            </div>
                          ))}
                          {exercises.length > 3 && (
                            <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                              +{exercises.length - 3} ещё
                            </div>
                          )}
                        </div>
                      )}
                    </GlassCard>
                  )
                })}
              </div>
            </div>
          )
        })()}


        {/* ── Последний вес ── */}
        {lastWeight && (
          <GlassCard className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(34,197,94,0.15)' }}
            >
              ⚖️
            </div>
            <div>
              <div className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                {lastWeight} кг
              </div>
              <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                Последний замер
              </div>
            </div>
          </GlassCard>
        )}

        {/* ── Empty state ── */}
        {(!recentSessions || recentSessions.length === 0) && !stats?.total_sessions && (
          <div className="flex flex-col items-center justify-center py-8">
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center mb-4 text-3xl"
              style={{ background: 'rgba(99,102,241,0.1)' }}
            >
              💪
            </div>
            <p className="text-base font-bold mb-1" style={{ color: 'var(--app-text)' }}>
              Начни тренироваться!
            </p>
            <p className="text-sm text-center px-8 mb-4" style={{ color: 'var(--app-hint)' }}>
              Записывай тренировки, отслеживай прогресс и ставь рекорды
            </p>
            <button
              onClick={() => setCreateOpen(true)}
              className="px-6 py-2.5 rounded-xl text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              Записать тренировку
            </button>
          </div>
        )}
      </div>

      {/* FAB */}
      <FAB onClick={() => setCreateOpen(true)} />

      {/* Bottom sheet создания тренировки */}
      <QuickWorkoutSheet open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}

/**
 * Определяет дни текущей недели, когда были тренировки.
 * Возвращает Set<number> — индексы дней (0=Пн, 6=Вс).
 */
function getWeekWorkoutDays(sessions: WorkoutSession[]): Set<number> {
  const result = new Set<number>()
  const now = new Date()
  // Начало недели (понедельник)
  const dayOfWeek = now.getDay() // 0=Вс, 1=Пн, ...
  const mondayOffset = dayOfWeek === 0 ? 6 : dayOfWeek - 1
  const monday = new Date(now)
  monday.setDate(now.getDate() - mondayOffset)
  monday.setHours(0, 0, 0, 0)

  for (const s of sessions) {
    if (!s.started_at) continue
    const d = new Date(s.started_at)
    if (d >= monday) {
      const day = d.getDay() // 0=Вс, 1=Пн, ...
      const idx = day === 0 ? 6 : day - 1 // конвертируем в 0=Пн
      result.add(idx)
    }
  }
  return result
}
