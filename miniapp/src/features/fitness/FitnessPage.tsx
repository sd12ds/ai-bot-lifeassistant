/**
 * Главная страница фитнес-модуля — дашборд.
 * Streak, карточка "Сегодня", недельная активность с прогрессом, быстрые действия, последние тренировки, статистика.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { TrendingUp, ChevronRight, History, Play, BarChart3, Ruler, Target, Sparkles, Trash2, Pencil, X } from 'lucide-react'
import {
  useFitnessStats, useSessions, useBodyMetrics, useNextWorkout, useFitnessGoals,
  useActivities, useDeleteActivity, useUpdateActivity, useDeleteSession, useUpdateSession,
  ACTIVITY_EMOJI, ACTIVITY_LABELS, type WorkoutSession, type Activity,
} from '../../api/fitness'
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
  const [showAllActivities, setShowAllActivities] = useState(false) // Раскрытие списка активностей
  // Стейты для удаления/редактирования
  const [confirmDeleteActivity, setConfirmDeleteActivity] = useState<number | null>(null)
  const [confirmDeleteSession, setConfirmDeleteSession] = useState<number | null>(null)
  const [editingActivity, setEditingActivity] = useState<Activity | null>(null)
  const [editingSession, setEditingSession] = useState<WorkoutSession | null>(null)

  // Данные
  const { data: stats } = useFitnessStats(30)
  const { data: recentSessions } = useSessions(7)
  const { data: bodyMetrics } = useBodyMetrics(30)
  // Следующая тренировка из активной программы
  const { data: nextWorkout } = useNextWorkout()
  // Цель тренировок в неделю
  const { data: fitnessGoal } = useFitnessGoals()
  // Активности (кардио, шаги и т.д.) — записанные через бота
  const { data: activities } = useActivities(7)
  // Мутации удаления/редактирования
  const deleteActivity = useDeleteActivity()
  const updateActivity = useUpdateActivity()
  const deleteSession = useDeleteSession()
  const updateSession = useUpdateSession()

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

            {/* Активности (кардио, растяжка и пр.) */}
            {stats.total_activities > 0 && (
              <div className="grid grid-cols-3 gap-3 text-center mt-2 pt-2 border-t border-white/[0.06]">
                <div>
                  <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                    {stats.total_activities}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    активностей
                  </div>
                </div>
                <div>
                  <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                    {stats.total_activity_time_min > 0 ? Math.round(stats.total_activity_time_min) : '—'}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    мин (кардио)
                  </div>
                </div>
                <div>
                  <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                    {stats.total_activity_calories > 0 ? Math.round(stats.total_activity_calories) : '—'}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    ккал
                  </div>
                </div>
              </div>
            )}

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

        {/* ── Активности (кардио, шаги, вело — из бота) ── */}
        {activities && activities.length > 0 && (
          <div>
            <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
              Активности
            </span>
            <div className="flex flex-col gap-2 mt-2">
              {(showAllActivities ? activities : activities.slice(0, 3)).map((a: Activity) => (
                <GlassCard key={a.id} className="p-3">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{ACTIVITY_EMOJI[a.activity_type] || '💪'}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                        {ACTIVITY_LABELS[a.activity_type] || a.activity_type}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                        {a.value} {a.unit}
                        {a.duration_min ? ` · ${a.duration_min} мин` : ''}
                        {a.calories_burned ? ` · ${Math.round(a.calories_burned)} ккал` : ''}
                      </div>
                    </div>
                    {/* Кнопки: редактировать + удалить */}
                    <div className="flex gap-1.5 shrink-0">
                      <button onClick={() => setEditingActivity(a)}
                        className="p-2.5 rounded-xl"
                        style={{ background: 'rgba(99,102,241,0.1)' }}>
                        <Pencil size={16} style={{ color: '#818cf8' }} />
                      </button>
                      <button onClick={() => setConfirmDeleteActivity(a.id)}
                        className="p-2.5 rounded-xl"
                        style={{ background: 'rgba(239,68,68,0.1)' }}>
                        <Trash2 size={16} style={{ color: '#ef4444' }} />
                      </button>
                    </div>
                  </div>
                  {/* Confirm удаления */}
                  {confirmDeleteActivity === a.id && (
                    <div className="flex items-center gap-2 mt-2 pt-2"
                      style={{ borderTop: '1px solid rgba(239,68,68,0.2)' }}>
                      <span className="text-xs flex-1" style={{ color: '#ef4444' }}>Удалить активность?</span>
                      <button onClick={() => { deleteActivity.mutate(a.id); setConfirmDeleteActivity(null) }}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold"
                        style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444' }}>Да</button>
                      <button onClick={() => setConfirmDeleteActivity(null)}
                        className="px-3 py-1.5 rounded-lg text-xs"
                        style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}>Отмена</button>
                    </div>
                  )}
                </GlassCard>
              ))}
            </div>
            {/* Кнопка раскрытия всех активностей */}
            {!showAllActivities && activities.length > 3 && (
              <button
                onClick={() => setShowAllActivities(true)}
                className="w-full mt-2 py-2 text-xs font-medium rounded-xl transition-colors"
                style={{ color: 'var(--app-accent)', background: 'var(--app-glass)' }}
              >
                Все активности ({activities.length})
              </button>
            )}
            {showAllActivities && activities.length > 3 && (
              <button
                onClick={() => setShowAllActivities(false)}
                className="w-full mt-2 py-2 text-xs font-medium rounded-xl transition-colors"
                style={{ color: 'var(--app-hint)', background: 'var(--app-glass)' }}
              >
                Свернуть
              </button>
            )}
          </div>
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
                        {/* Кнопки: изменить + удалить тренировку */}
                        <div className="flex gap-1.5 shrink-0">
                          <button onClick={() => setEditingSession(s)}
                            className="p-2.5 rounded-xl"
                            style={{ background: 'rgba(99,102,241,0.1)' }}>
                            <Pencil size={16} style={{ color: '#818cf8' }} />
                          </button>
                          <button onClick={() => setConfirmDeleteSession(s.id)}
                            className="p-2.5 rounded-xl"
                            style={{ background: 'rgba(239,68,68,0.1)' }}>
                            <Trash2 size={16} style={{ color: '#ef4444' }} />
                          </button>
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
                      {/* Confirm удаления тренировки */}
                      {confirmDeleteSession === s.id && (
                        <div className="flex items-center gap-2 mt-2 pt-2"
                          style={{ borderTop: '1px solid rgba(239,68,68,0.2)' }}>
                          <span className="text-xs flex-1" style={{ color: '#ef4444' }}>Удалить тренировку?</span>
                          <button onClick={() => { deleteSession.mutate(s.id); setConfirmDeleteSession(null) }}
                            className="px-3 py-1.5 rounded-lg text-xs font-bold"
                            style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444' }}>Да</button>
                          <button onClick={() => setConfirmDeleteSession(null)}
                            className="px-3 py-1.5 rounded-lg text-xs"
                            style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}>Отмена</button>
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

      {/* ── Модалка редактирования тренировки ── */}
      {editingSession && (
        <EditSessionSheet
          session={editingSession}
          onSave={(data) => {
            updateSession.mutate({ id: editingSession.id, ...data })
            setEditingSession(null)
          }}
          onClose={() => setEditingSession(null)}
        />
      )}

      {/* ── Модалка редактирования активности ── */}
      {editingActivity && (
        <EditActivitySheet
          activity={editingActivity}
          onSave={(data) => {
            updateActivity.mutate({ id: editingActivity.id, ...data })
            setEditingActivity(null)
          }}
          onClose={() => setEditingActivity(null)}
        />
      )}

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


/** ─── Форма редактирования активности (overlay) ─── */
function EditActivitySheet({ activity, onSave, onClose }: {
  activity: Activity
  onSave: (data: Record<string, any>) => void
  onClose: () => void
}) {
  // Локальный стейт полей формы
  const [value, setValue] = useState(String(activity.value || ''))
  const [unit, setUnit] = useState(activity.unit || 'min')
  const [durationMin, setDurationMin] = useState(String(activity.duration_min || ''))
  const [calories, setCalories] = useState(String(activity.calories_burned || ''))
  const [notes, setNotes] = useState(activity.notes || '')

  const handleSubmit = () => {
    const data: Record<string, any> = {
      activity_type: activity.activity_type,
      value: parseFloat(value) || 0,
      unit,
    }
    if (durationMin) data.duration_min = parseFloat(durationMin)
    if (calories) data.calories_burned = parseFloat(calories)
    if (notes) data.notes = notes
    onSave(data)
  }

  // Стиль полей ввода
  const inputStyle = {
    background: 'rgba(255,255,255,0.06)',
    color: 'var(--app-text)',
    border: '1px solid rgba(255,255,255,0.1)',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-lg rounded-t-2xl p-4 pb-8"
        style={{ background: 'var(--app-bg, #1a1a2e)' }}>
        {/* Заголовок */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
            Изменить активность
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg"
            style={{ background: 'rgba(255,255,255,0.06)' }}>
            <X size={16} style={{ color: 'var(--app-hint)' }} />
          </button>
        </div>

        {/* Тип (readonly) */}
        <div className="mb-3">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Тип</label>
          <div className="px-3 py-2 rounded-lg text-sm"
            style={{ ...inputStyle, opacity: 0.6 }}>
            {ACTIVITY_EMOJI[activity.activity_type] || '💪'}{' '}
            {ACTIVITY_LABELS[activity.activity_type] || activity.activity_type}
          </div>
        </div>

        {/* Значение + единица в одну строку */}
        <div className="flex gap-2 mb-3">
          <div className="flex-1">
            <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Значение</label>
            <input type="number" value={value} onChange={(e) => setValue(e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={inputStyle} />
          </div>
          <div className="w-24">
            <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Ед.</label>
            <select value={unit} onChange={(e) => setUnit(e.target.value)}
              className="w-full px-2 py-2 rounded-lg text-sm outline-none"
              style={inputStyle}>
              <option value="min">мин</option>
              <option value="km">км</option>
              <option value="m">м</option>
              <option value="steps">шагов</option>
            </select>
          </div>
        </div>

        {/* Длительность */}
        <div className="mb-3">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Длительность (мин)</label>
          <input type="number" value={durationMin} onChange={(e) => setDurationMin(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={inputStyle} placeholder="Необязательно" />
        </div>

        {/* Калории */}
        <div className="mb-3">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Калории</label>
          <input type="number" value={calories} onChange={(e) => setCalories(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={inputStyle} placeholder="Необязательно" />
        </div>

        {/* Заметка */}
        <div className="mb-4">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Заметка</label>
          <input type="text" value={notes} onChange={(e) => setNotes(e.target.value)}
            className="w-full px-3 py-2 rounded-lg text-sm outline-none"
            style={inputStyle} placeholder="Необязательно" />
        </div>

        {/* Кнопка сохранения */}
        <button onClick={handleSubmit}
          className="w-full py-3 rounded-xl text-sm font-bold"
          style={{ background: 'rgba(99,102,241,0.3)', color: '#a5b4fc' }}>
          Сохранить
        </button>
      </div>
    </div>
  )
}


/** ─── Типы тренировок для выбора ─── */
const SESSION_TYPE_OPTIONS = [
  { value: 'strength', label: '🏋️ Силовая' },
  { value: 'cardio', label: '🏃 Кардио' },
  { value: 'home', label: '🏠 Домашняя' },
  { value: 'functional', label: '⚡ Функциональная' },
  { value: 'stretching', label: '🧘 Растяжка' },
]

/** ─── Форма редактирования тренировки (overlay) ─── */
function EditSessionSheet({ session, onSave, onClose }: {
  session: WorkoutSession
  onSave: (data: Record<string, any>) => void
  onClose: () => void
}) {
  // Локальный стейт полей
  const [name, setName] = useState(session.name || '')
  const [workoutType, setWorkoutType] = useState(session.workout_type || 'strength')
  const [notes, setNotes] = useState(session.notes || '')
  const [moodBefore, setMoodBefore] = useState(session.mood_before || 0)
  const [moodAfter, setMoodAfter] = useState(session.mood_after || 0)

  const handleSubmit = () => {
    const data: Record<string, any> = {}
    if (name !== session.name) data.name = name
    if (workoutType !== session.workout_type) data.workout_type = workoutType
    if (notes !== (session.notes || '')) data.notes = notes
    if (moodBefore && moodBefore !== session.mood_before) data.mood_before = moodBefore
    if (moodAfter && moodAfter !== session.mood_after) data.mood_after = moodAfter
    if (Object.keys(data).length > 0) onSave(data)
    else onClose()
  }

  const inputStyle = {
    background: 'rgba(255,255,255,0.06)',
    color: 'var(--app-text)',
    border: '1px solid rgba(255,255,255,0.1)',
  }

  // Рендер кнопок настроения (1-5)
  const MoodPicker = ({ value, onChange, label }: { value: number; onChange: (v: number) => void; label: string }) => (
    <div className="mb-3">
      <label className="text-xs mb-1.5 block" style={{ color: 'var(--app-hint)' }}>{label}</label>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((v) => (
          <button key={v} onClick={() => onChange(v)}
            className="w-10 h-10 rounded-xl text-sm font-bold"
            style={{
              background: value === v ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
              color: value === v ? '#a5b4fc' : 'var(--app-hint)',
            }}>
            {v}
          </button>
        ))}
      </div>
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-lg rounded-t-2xl p-4 pb-8 max-h-[80vh] overflow-y-auto"
        style={{ background: 'var(--app-bg, #1a1a2e)' }}>
        {/* Заголовок */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
            Изменить тренировку
          </h3>
          <button onClick={onClose} className="p-1.5 rounded-lg"
            style={{ background: 'rgba(255,255,255,0.06)' }}>
            <X size={16} style={{ color: 'var(--app-hint)' }} />
          </button>
        </div>

        {/* Название */}
        <div className="mb-3">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Название</label>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
            style={inputStyle} />
        </div>

        {/* Тип */}
        <div className="mb-3">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Тип</label>
          <select value={workoutType} onChange={(e) => setWorkoutType(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
            style={inputStyle}>
            {SESSION_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Настроение до */}
        <MoodPicker value={moodBefore} onChange={setMoodBefore} label="Настроение до (1-5)" />

        {/* Настроение после */}
        <MoodPicker value={moodAfter} onChange={setMoodAfter} label="Настроение после (1-5)" />

        {/* Заметки */}
        <div className="mb-4">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Заметки</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg text-sm outline-none resize-none"
            rows={3}
            style={inputStyle} placeholder="Как прошла тренировка..." />
        </div>

        {/* Кнопка */}
        <button onClick={handleSubmit}
          className="w-full py-3 rounded-xl text-sm font-bold"
          style={{ background: 'rgba(99,102,241,0.3)', color: '#a5b4fc' }}>
          Сохранить
        </button>
      </div>
    </div>
  )
}
