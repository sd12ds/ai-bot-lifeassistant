/**
 * История тренировок — детальные карточки.
 * Название, тип (свободная/по программе), дата+время, упражнения с весами.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ChevronLeft, ChevronDown, ChevronUp,
  Dumbbell, RotateCcw, FileText, Trash2,
} from 'lucide-react'
import { useSessions, useRepeatSession, useDeleteSession, type WorkoutSession, type WorkoutSet } from '../../api/fitness'
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
  const repeatSession = useRepeatSession()
  const deleteSession = useDeleteSession()
  // ID тренировки для подтверждения удаления
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)

  // Фильтруем пустые сессии
  const sessions = allSessions?.filter(s => {
    const hasSets = (s.sets?.length || 0) > 0
    const hasVolume = (s.total_volume_kg || 0) > 0
    const hasRealDuration = (s.total_duration_sec || 0) >= 30
    return hasSets || hasVolume || hasRealDuration
  })

  const handleRepeat = async (id: number) => {
    try { await repeatSession.mutateAsync(id) } catch (e) { console.error(e) }
  }

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
            onRepeat={handleRepeat}
            onDelete={(id) => setConfirmDeleteId(id)}
            isConfirming={confirmDeleteId === s.id}
            onConfirmDelete={() => {
              deleteSession.mutate(s.id)
              setConfirmDeleteId(null)
            }}
            onCancelDelete={() => setConfirmDeleteId(null)}
          />
        ))}
      </div>
    </div>
  )
}


/** ─── Карточка тренировки ─── */
function SessionCard({ session, onRepeat, onDelete, isConfirming, onConfirmDelete, onCancelDelete }: {
  session: WorkoutSession
  onRepeat: (id: number) => void
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
          <button onClick={() => onRepeat(session.id)}
            className="p-2 rounded-xl"
            style={{ background: 'rgba(99,102,241,0.1)' }}>
            <RotateCcw size={14} style={{ color: '#818cf8' }} />
          </button>
          <button onClick={() => onDelete(session.id)}
            className="p-2 rounded-xl"
            style={{ background: 'rgba(239,68,68,0.1)' }}>
            <Trash2 size={14} style={{ color: '#ef4444' }} />
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
