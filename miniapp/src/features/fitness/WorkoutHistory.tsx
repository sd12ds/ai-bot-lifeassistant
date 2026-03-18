/**
 * История тренировок — детальные карточки.
 * Название, тип (свободная/по программе), дата+время, упражнения с весами.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ChevronLeft, ChevronDown, ChevronUp,
  Dumbbell, Pencil, FileText, Trash2,
} from 'lucide-react'
import {
  useSessions, useDeleteSession, useUpdateSession,
  useUpdateSet, useDeleteSet, useAddSet,
  type WorkoutSession, type WorkoutSet,
} from '../../api/fitness'
import { X, Plus, Minus } from 'lucide-react'
import { GlassCard } from '../../shared/ui/GlassCard'

// Типы тренировок
const TYPE_LABELS: Record<string, { label: string; icon: string }> = {
  strength:    { label: 'Силовая',        icon: '🏋️' },
  cardio:      { label: 'Кардио',         icon: '🏃' },
  home:        { label: 'Домашняя',       icon: '🏠' },
  functional:  { label: 'Функциональная', icon: '⚡' },
  stretching:  { label: 'Растяжка',       icon: '🧘' },
}

const PERIODS = [
  { value: 7,  label: '7 дней' },
  { value: 14, label: '14 дней' },
  { value: 30, label: '30 дней' },
  { value: 90, label: '3 мес' },
]

/** Дата: «Ср, 12 мар» */
function fmtDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' })
}

/** Время: «22:30» */
function fmtTime(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

/** Длительность */
function fmtDuration(sec: number | null): string {
  if (!sec || sec <= 0) return ''
  const m = Math.round(sec / 60)
  if (m < 1) return ''
  if (m < 60) return `${m} мин`
  return `${Math.floor(m / 60)}ч ${m % 60}мин`
}

/** Группировка подходов по упражнениям */
function groupExercises(sets: WorkoutSet[]) {
  const map = new Map<number, { name: string; sets: WorkoutSet[] }>()
  for (const s of sets) {
    if (!map.has(s.exercise_id)) {
      map.set(s.exercise_id, { name: s.exercise_name || `Упражнение #${s.exercise_id}`, sets: [] })
    }
    map.get(s.exercise_id)!.sets.push(s)
  }
  return Array.from(map.values())
}

/**
 * Человекочитаемая сводка по подходам одного упражнения.
 * Примеры: «4 подх × 80 кг × 8 повт», «3 подх × 10 повт», «3 подх × 5 км»
 */
function exerciseSummary(sets: WorkoutSet[]): string {
  // Группируем по уникальным параметрам
  const combos = sets.map(s => {
    const parts: string[] = []
    if (s.weight_kg) parts.push(`${s.weight_kg} кг`)
    if (s.reps) parts.push(`${s.reps} повт`)
    if (s.distance_m) {
      parts.push(s.distance_m >= 1000 ? `${(s.distance_m / 1000).toFixed(1)} км` : `${s.distance_m} м`)
    }
    if (s.duration_sec && !s.reps && !s.distance_m) parts.push(`${s.duration_sec} сек`)
    return parts.join(' × ')
  })

  // Уникальные комбинации
  const unique = combos.filter((v, i, a) => a.indexOf(v) === i)
  if (unique.length === 1) return `${sets.length} подх × ${unique[0]}`
  // Разные параметры — перечисляем
  return unique.map((u) => {
    const cnt = combos.filter(c => c === u).length
    return `${cnt}× ${u}`
  }).filter((v, i, a) => a.indexOf(v) === i).join(', ')
}

export function WorkoutHistory() {
  const navigate = useNavigate()
  const [days, setDays] = useState(30)
  const { data: allSessions, isLoading } = useSessions(days)
  const deleteSession = useDeleteSession()
  const updateSession = useUpdateSession()
  // ID тренировки для подтверждения удаления
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  // Тренировка для редактирования
  const [editingSession, setEditingSession] = useState<WorkoutSession | null>(null)

  // Фильтруем пустые сессии
  const sessions = allSessions?.filter(s => {
    const hasSets = (s.sets?.length || 0) > 0
    const hasVolume = (s.total_volume_kg || 0) > 0
    const hasRealDuration = (s.total_duration_sec || 0) >= 30
    return hasSets || hasVolume || hasRealDuration
  })


  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-2">
        <button onClick={() => navigate('/fitness')} className="p-1">
          <ChevronLeft size={24} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
          История тренировок
        </h1>
      </div>

      {/* Фильтр */}
      <div className="flex gap-2 px-4 pb-3">
        {PERIODS.map((p) => (
          <button key={p.value} onClick={() => setDays(p.value)}
            className="px-3 py-1.5 rounded-full text-xs font-medium"
            style={{
              background: days === p.value ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
              color: days === p.value ? '#a5b4fc' : 'var(--app-hint)',
            }}>
            {p.label}
          </button>
        ))}
      </div>

      {/* Список */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-3">
        {isLoading && (
          <div className="text-center py-10 text-sm" style={{ color: 'var(--app-hint)' }}>Загрузка...</div>
        )}

        {!isLoading && (!sessions || sessions.length === 0) && (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-16 h-16 rounded-full flex items-center justify-center mb-3"
              style={{ background: 'rgba(99,102,241,0.1)' }}>
              <Dumbbell size={28} style={{ color: '#818cf8' }} />
            </div>
            <p className="text-sm font-medium mb-1" style={{ color: 'var(--app-text)' }}>Нет тренировок</p>
            <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
              За выбранный период тренировок не найдено
            </p>
          </div>
        )}

        {sessions?.map((s) => (
          <SessionCard
            key={s.id}
            session={s}
            onEdit={(sess) => setEditingSession(sess)}
            onDelete={(id) => setConfirmDeleteId(id)}
            isConfirming={confirmDeleteId === s.id}
            onConfirmDelete={() => {
              deleteSession.mutate(s.id)
              setConfirmDeleteId(null)
            }}
            onCancelDelete={() => setConfirmDeleteId(null)}
          />
        ))}

        {/* Модалка редактирования тренировки */}
        {editingSession && (
          <EditSessionOverlay
            session={editingSession}
            onSave={(data) => {
              updateSession.mutate({ id: editingSession.id, ...data })
              setEditingSession(null)
            }}
            onClose={() => setEditingSession(null)}
          />
        )}
      </div>
    </div>
  )
}


/** ─── Карточка тренировки ─── */
function SessionCard({ session, onEdit, onDelete, isConfirming, onConfirmDelete, onCancelDelete }: {
  session: WorkoutSession
  onEdit: (s: WorkoutSession) => void
  onDelete: (id: number) => void
  isConfirming: boolean
  onConfirmDelete: () => void
  onCancelDelete: () => void
}) {
  const [expanded, setExpanded] = useState(false)

  const type = TYPE_LABELS[session.workout_type] || { label: session.workout_type, icon: '🏋️' }
  const dateStr = fmtDate(session.started_at)
  const startTime = fmtTime(session.started_at)
  const endTime = fmtTime(session.ended_at)
  // Интервал времени
  const timeStr = startTime && endTime && startTime !== endTime
    ? `${startTime} – ${endTime}` : startTime || ''
  const duration = fmtDuration(session.total_duration_sec)
  const sets = session.sets || []
  const exercises = groupExercises(sets)

  // Тип: по программе или свободная
  const isProgram = session.name && !session.name.startsWith('Тренировка ')
  const badge = isProgram ? 'По программе' : 'Свободная'
  const badgeColor = isProgram ? '#fb923c' : '#818cf8'

  return (
    <GlassCard>
      {/* ── Заголовок ── */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2.5">
          <span className="text-xl">{type.icon}</span>
          <div>
            <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
              {session.name || type.label}
            </div>
            <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
              <span className="px-1.5 py-0.5 rounded text-[9px] font-bold"
                style={{ background: `${badgeColor}22`, color: badgeColor }}>
                {badge}
              </span>
              <span className="text-[11px]" style={{ color: 'var(--app-hint)' }}>
                {dateStr}
                {timeStr ? ` · ${timeStr}` : ''}
                {duration ? ` · ${duration}` : ''}
              </span>
            </div>
          </div>
        </div>
        <div className="flex gap-1.5 shrink-0">
          <button onClick={() => onEdit(session)}
            className="p-2.5 rounded-xl"
            style={{ background: 'rgba(99,102,241,0.1)' }}>
            <Pencil size={16} style={{ color: '#818cf8' }} />
          </button>
          <button onClick={() => onDelete(session.id)}
            className="p-2.5 rounded-xl"
            style={{ background: 'rgba(239,68,68,0.1)' }}>
            <Trash2 size={16} style={{ color: '#ef4444' }} />
          </button>
        </div>
      </div>

      {/* ── Упражнения ── */}
      {exercises.length > 0 ? (
        <div className="space-y-1">
          {exercises.slice(0, expanded ? exercises.length : 4).map((ex, idx) => (
            <div key={idx} className="py-1.5 px-2 rounded-lg"
              style={{ background: idx % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent' }}>
              <div className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>
                {ex.name}
              </div>
              <div className="text-[10px] mt-0.5" style={{ color: 'var(--app-hint)' }}>
                {exerciseSummary(ex.sets)}
              </div>
            </div>
          ))}

          {exercises.length > 4 && (
            <button onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 w-full justify-center py-1.5 text-[11px] font-medium"
              style={{ color: '#818cf8' }}>
              {expanded
                ? <><ChevronUp size={14} /> Свернуть</>
                : <><ChevronDown size={14} /> Ещё {exercises.length - 4} упражнений</>}
            </button>
          )}
        </div>
      ) : (
        <div className="text-[11px] py-1" style={{ color: 'var(--app-hint)' }}>
          Подходы не записаны
        </div>
      )}

      {/* Подтверждение удаления */}
      {isConfirming && (
        <div className="flex items-center gap-2 mt-2 pt-2"
          style={{ borderTop: '1px solid rgba(239,68,68,0.2)' }}>
          <span className="text-xs flex-1" style={{ color: '#ef4444' }}>Удалить тренировку?</span>
          <button onClick={onConfirmDelete}
            className="px-3 py-1.5 rounded-lg text-xs font-bold"
            style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444' }}>
            Да
          </button>
          <button onClick={onCancelDelete}
            className="px-3 py-1.5 rounded-lg text-xs"
            style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-hint)' }}>
            Отмена
          </button>
        </div>
      )}

      {/* Настроение */}
      {(session.mood_before || session.mood_after) && (
        <div className="text-[10px] mt-2 pt-1.5"
          style={{ color: 'var(--app-hint)', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          {session.mood_before ? `Настроение до: ${session.mood_before}/5` : ''}
          {session.mood_before && session.mood_after ? ' → ' : ''}
          {session.mood_after ? `после: ${session.mood_after}/5` : ''}
        </div>
      )}

      {/* Заметки */}
      {session.notes && (
        <div className="flex items-start gap-1.5 text-[10px] mt-1.5 px-2 py-1.5 rounded-lg"
          style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--app-hint)' }}>
          <FileText size={10} className="shrink-0 mt-0.5" />
          <span>{session.notes}</span>
        </div>
      )}
    </GlassCard>
  )
}


/** Типы тренировок для выбора */
const SESSION_TYPES = [
  { value: 'strength', label: '🏋️ Силовая' },
  { value: 'cardio', label: '🏃 Кардио' },
  { value: 'home', label: '🏠 Домашняя' },
  { value: 'functional', label: '⚡ Функциональная' },
  { value: 'stretching', label: '🧘 Растяжка' },
]

/** Форма редактирования тренировки — подходы (вес + повторения), +/- подход */
function EditSessionOverlay({ session, onSave, onClose }: {
  session: WorkoutSession
  onSave: (data: Record<string, any>) => void
  onClose: () => void
}) {
  // Название и тип тренировки
  const [name, setName] = useState(session.name || '')
  const [workoutType, setWorkoutType] = useState(session.workout_type || 'strength')

  // Хуки мутаций для подходов
  const updateSet = useUpdateSet()
  const deleteSet = useDeleteSet()
  const addSet = useAddSet()

  // Группируем подходы по упражнениям
  const exercises = groupExercises(session.sets || [])

  // Сохранение названия/типа
  const handleSaveHeader = () => {
    const data: Record<string, any> = {}
    if (name !== session.name) data.name = name
    if (workoutType !== session.workout_type) data.workout_type = workoutType
    if (Object.keys(data).length > 0) onSave(data)
    else onClose()
  }

  // Обновление конкретного подхода (вес или повторения)
  const handleUpdateSet = (setId: number, field: string, value: number | null) => {
    updateSet.mutate({ id: setId, [field]: value })
  }

  // Удаление подхода
  const handleDeleteSet = (setId: number) => {
    deleteSet.mutate(setId)
  }

  // Добавление подхода к упражнению (копирует параметры последнего)
  const handleAddSet = (exerciseId: number, lastSet: WorkoutSet) => {
    addSet.mutate({
      sessionId: session.id,
      dto: {
        exercise_id: exerciseId,
        reps: lastSet.reps ?? undefined,
        weight_kg: lastSet.weight_kg ?? undefined,
        duration_sec: lastSet.duration_sec ?? undefined,
        distance_m: lastSet.distance_m ?? undefined,
        set_type: lastSet.set_type || 'working',
      },
    })
  }

  const inputStyle = {
    background: 'rgba(255,255,255,0.06)',
    color: 'var(--app-text)',
    border: '1px solid rgba(255,255,255,0.1)',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-full max-w-lg rounded-t-2xl p-4 pb-8 max-h-[85vh] overflow-y-auto"
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
            className="w-full px-3 py-2.5 rounded-lg text-sm outline-none" style={inputStyle} />
        </div>

        {/* Тип */}
        <div className="mb-4">
          <label className="text-xs mb-1 block" style={{ color: 'var(--app-hint)' }}>Тип</label>
          <select value={workoutType} onChange={(e) => setWorkoutType(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg text-sm outline-none" style={inputStyle}>
            {SESSION_TYPES.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* Упражнения с подходами */}
        {exercises.length > 0 ? (
          <div className="space-y-4 mb-4">
            {exercises.map((ex, exIdx) => (
              <div key={exIdx} className="rounded-xl p-3"
                style={{ background: 'rgba(255,255,255,0.03)' }}>
                {/* Название упражнения */}
                <div className="text-xs font-bold mb-2" style={{ color: 'var(--app-text)' }}>
                  {ex.name}
                </div>

                {/* Заголовки столбцов */}
                <div className="flex items-center gap-2 mb-1.5 px-1">
                  <span className="text-[10px] w-8 text-center" style={{ color: 'var(--app-hint)' }}>#</span>
                  <span className="text-[10px] flex-1 text-center" style={{ color: 'var(--app-hint)' }}>Вес (кг)</span>
                  <span className="text-[10px] flex-1 text-center" style={{ color: 'var(--app-hint)' }}>Повторы</span>
                  <span className="w-8" />
                </div>

                {/* Подходы */}
                {ex.sets.map((s, sIdx) => (
                  <div key={s.id} className="flex items-center gap-2 mb-1.5">
                    {/* Номер подхода */}
                    <span className="text-[11px] w-8 text-center font-medium"
                      style={{ color: 'var(--app-hint)' }}>{sIdx + 1}</span>

                    {/* Вес */}
                    <input
                      type="number"
                      inputMode="decimal"
                      defaultValue={s.weight_kg ?? ''}
                      onBlur={(e) => {
                        const v = e.target.value ? parseFloat(e.target.value) : null
                        if (v !== s.weight_kg) handleUpdateSet(s.id, 'weight_kg', v)
                      }}
                      className="flex-1 px-2 py-2 rounded-lg text-sm text-center outline-none"
                      style={inputStyle}
                      placeholder="—"
                    />

                    {/* Повторения */}
                    <input
                      type="number"
                      inputMode="numeric"
                      defaultValue={s.reps ?? ''}
                      onBlur={(e) => {
                        const v = e.target.value ? parseInt(e.target.value) : null
                        if (v !== s.reps) handleUpdateSet(s.id, 'reps', v)
                      }}
                      className="flex-1 px-2 py-2 rounded-lg text-sm text-center outline-none"
                      style={inputStyle}
                      placeholder="—"
                    />

                    {/* Удалить подход */}
                    <button onClick={() => handleDeleteSet(s.id)}
                      className="w-8 h-8 flex items-center justify-center rounded-lg shrink-0"
                      style={{ background: 'rgba(239,68,68,0.1)' }}>
                      <Minus size={14} style={{ color: '#ef4444' }} />
                    </button>
                  </div>
                ))}

                {/* Кнопка добавить подход */}
                <button
                  onClick={() => handleAddSet(ex.sets[0].exercise_id, ex.sets[ex.sets.length - 1])}
                  className="flex items-center gap-1.5 w-full justify-center py-2 mt-1 rounded-lg text-xs font-medium"
                  style={{ background: 'rgba(99,102,241,0.08)', color: '#818cf8' }}>
                  <Plus size={14} /> Добавить подход
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs py-4 text-center mb-4" style={{ color: 'var(--app-hint)' }}>
            Подходы не записаны
          </div>
        )}

        {/* Кнопка сохранить название/тип */}
        <button onClick={handleSaveHeader}
          className="w-full py-3 rounded-xl text-sm font-bold"
          style={{ background: 'rgba(99,102,241,0.3)', color: '#a5b4fc' }}>
          Сохранить
        </button>
      </div>
    </div>
  )
}
