/**
 * Редактор программы тренировок v3.
 * Фиксы: плотный фон модала, weekday сохраняется, редактирование упражнений дня.
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Save, Plus, Trash2, Edit3, Calendar, Dumbbell,
  Loader2, Search, GripVertical,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { usePrograms, useTemplates, useExerciseSearch } from '../../api/fitness'
import type { Program, ProgramDay } from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'
import { apiClient } from '../../api/client'

// Названия дней недели
const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'] as const

// Тип упражнения в дне (для локального редактирования)
interface DayExercise {
  exercise_id: number
  exercise_name: string
  sets: number
  reps: number | null
  weight_kg: number | null
  rest_sec: number
}

export function ProgramEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const programId = Number(id)

  // Данные
  const { data: programs, refetch: refetchPrograms } = usePrograms()
  const { data: templates } = useTemplates()
  const qc = useQueryClient()
  const program = programs?.find((p: Program) => p.id === programId) as Program | undefined

  // Состояние дней
  const [days, setDays] = useState<ProgramDay[]>([])
  const [saving, setSaving] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [toast, setToast] = useState('')

  // Модал редактирования дня
  const [editingDay, setEditingDay] = useState<ProgramDay | null>(null)
  const [editName, setEditName] = useState('')
  const [editWeekday, setEditWeekday] = useState<number | null>(null)
  const [editStartTime, setEditStartTime] = useState<string>('')
  const [editEndTime, setEditEndTime] = useState<string>('')
  const [editExercises, setEditExercises] = useState<DayExercise[]>([])
  const [showTemplateSelect, setShowTemplateSelect] = useState(false)

  // Поиск упражнений для добавления
  const [exSearchQuery, setExSearchQuery] = useState('')
  const [showExSearch, setShowExSearch] = useState(false)
  const { data: searchResults } = useExerciseSearch(exSearchQuery)

  // Модал добавления дня
  const [showAddDay, setShowAddDay] = useState(false)
  const [newDayName, setNewDayName] = useState('')
  const [newDayWeekday, setNewDayWeekday] = useState<number | null>(null)

  // Инициализация дней из программы
  useEffect(() => {
    if (program?.days) {
      setDays([...program.days].sort((a, b) => a.day_number - b.day_number))
    }
  }, [program])

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(''), 2500)
  }

  // Получить шаблон
  const getTemplate = (templateId: number | null) => {
    if (!templateId || !templates) return null
    return templates.find((t: any) => t.id === templateId)
  }

  // Открыть редактирование дня
  const openEdit = (day: ProgramDay) => {
    setEditingDay(day)
    setEditName(day.day_name || '')
    setEditWeekday(day.weekday ?? null)
    setEditStartTime(day.preferred_start_time || '')
    setEditEndTime(day.preferred_end_time || '')
    setShowTemplateSelect(false)
    setShowExSearch(false)
    setExSearchQuery('')
    // Загружаем упражнения из привязанного шаблона
    const tpl = getTemplate(day.template_id)
    if (tpl?.exercises) {
      setEditExercises(tpl.exercises.map((ex: any) => ({
        exercise_id: ex.exercise_id,
        exercise_name: ex.exercise_name || `#${ex.exercise_id}`,
        sets: ex.sets || 3,
        reps: ex.reps || null,
        weight_kg: ex.weight_kg || null,
        rest_sec: ex.rest_sec || 60,
      })))
    } else {
      setEditExercises([])
    }
  }

  // Сохранить день
  const handleSaveDay = async () => {
    if (!editingDay) return
    setSaving(true)
    try {
      const body: Record<string, unknown> = {
        day_name: editName || null,
        weekday: editWeekday,
        preferred_start_time: editStartTime || null,
        preferred_end_time: editEndTime || null,
      }
      // Передаём упражнения — бэкенд пересоздаст шаблон
      if (editExercises.length > 0) {
        body.exercises = editExercises.map(ex => ({
          exercise_id: ex.exercise_id,
          sets: ex.sets,
          reps: ex.reps,
          weight_kg: ex.weight_kg,
          rest_sec: ex.rest_sec,
        }))
      }
      await apiClient.put(`/fitness/programs/${programId}/days/${editingDay.id}`, body)
      await refetchPrograms()
      qc.invalidateQueries({ queryKey: ['fitness', 'programs'] })
      qc.invalidateQueries({ queryKey: ['fitness', 'templates'] })
      setEditingDay(null)
      showToast('Сохранено ✓')
    } catch (e) {
      console.error('Ошибка сохранения:', e)
      showToast('Ошибка сохранения')
    } finally {
      setSaving(false)
    }
  }

  // Удалить день
  const handleDeleteDay = async (dayId: number) => {
    setSaving(true)
    try {
      await apiClient.delete(`/fitness/programs/${programId}/days/${dayId}`)
      await refetchPrograms()
      showToast('День удалён')
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  // Добавить день
  const handleAddDay = async () => {
    if (!newDayName.trim()) return
    setSaving(true)
    try {
      await apiClient.post(`/fitness/programs/${programId}/days`, {
        day_name: newDayName.trim(),
        weekday: newDayWeekday,
      })
      await refetchPrograms()
      qc.invalidateQueries({ queryKey: ['fitness', 'templates'] })
      setShowAddDay(false)
      setNewDayName('')
      setNewDayWeekday(null)
      showToast('День добавлен ✓')
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  // Добавить упражнение в редактируемый день
  const addExercise = (ex: any) => {
    setEditExercises(prev => [...prev, {
      exercise_id: ex.id,
      exercise_name: ex.name,
      sets: 3,
      reps: 10,
      weight_kg: null,
      rest_sec: 60,
    }])
    setShowExSearch(false)
    setExSearchQuery('')
  }

  // Удалить упражнение
  const removeExercise = (idx: number) => {
    setEditExercises(prev => prev.filter((_, i) => i !== idx))
  }

  // Обновить параметры упражнения
  const updateExercise = (idx: number, field: keyof DayExercise, value: number | null) => {
    setEditExercises(prev => prev.map((ex, i) => i === idx ? { ...ex, [field]: value } : ex))
  }

  // Загрузить упражнения из шаблона
  const loadFromTemplate = (tplId: number) => {
    const tpl = getTemplate(tplId)
    if (tpl?.exercises) {
      setEditExercises(tpl.exercises.map((ex: any) => ({
        exercise_id: ex.exercise_id,
        exercise_name: ex.exercise_name || `#${ex.exercise_id}`,
        sets: ex.sets || 3,
        reps: ex.reps || null,
        weight_kg: ex.weight_kg || null,
        rest_sec: ex.rest_sec || 60,
      })))
    }
    setShowTemplateSelect(false)
  }

  // Синхронизация с календарём
  const handleSyncCalendar = async () => {
    setSyncing(true)
    try {
      await apiClient.post(`/fitness/programs/${programId}/sync-calendar`)
      showToast('Календарь синхронизирован ✓')
    } catch (e) {
      console.error(e)
      showToast('Ошибка синхронизации')
    } finally {
      setSyncing(false)
    }
  }

  // Тап на слот недельной сетки
  const handleSlotTap = (wdIdx: number) => {
    const day = days.find(d => d.weekday === wdIdx)
    if (day) openEdit(day)
  }

  if (!program) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 size={32} className="animate-spin" style={{ color: '#a5b4fc' }} />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* ── Шапка ── */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-2">
        <button onClick={() => navigate('/fitness/programs')} className="p-2 -ml-2">
          <ArrowLeft size={22} style={{ color: 'var(--app-text)' }} />
        </button>
        <div className="flex-1">
          <h1 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
            {program.name}
          </h1>
          <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
            {program.days_per_week} дн/нед · {program.difficulty}
            {program.is_active && <span style={{ color: '#22c55e' }}> · Активна</span>}
          </p>
        </div>
        {program.is_active && (
          <button onClick={handleSyncCalendar} disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium"
            style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}>
            {syncing ? <Loader2 size={14} className="animate-spin" /> : <Calendar size={14} />}
            Синхр.
          </button>
        )}
      </div>

      {/* ── Контент ── */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
        {/* Недельная сетка */}
        <GlassCard>
          <div className="text-xs font-medium mb-3" style={{ color: 'var(--app-hint)' }}>
            Недельное расписание
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {WEEKDAYS.map((name, idx) => (
              <div key={idx} className="text-center text-[10px] font-bold pb-1"
                style={{ color: idx >= 5 ? '#fb923c' : 'var(--app-hint)' }}>
                {name}
              </div>
            ))}
            {WEEKDAYS.map((_, wdIdx) => {
              const ad = days.find(d => d.weekday === wdIdx)
              return (
                <button key={wdIdx} onClick={() => ad && handleSlotTap(wdIdx)}
                  className="aspect-square rounded-xl flex flex-col items-center justify-center text-[9px] font-bold transition-all"
                  style={{
                    background: ad
                      ? 'linear-gradient(135deg, rgba(251,146,60,0.3), rgba(234,88,12,0.2))'
                      : 'rgba(255,255,255,0.03)',
                    border: ad ? '1.5px solid rgba(251,146,60,0.4)' : '1px solid rgba(255,255,255,0.06)',
                    color: ad ? '#fb923c' : 'var(--app-hint)',
                    cursor: ad ? 'pointer' : 'default',
                  }}>
                  {ad ? (
                    <>
                      <span className="text-[11px]">{ad.day_number}</span>
                      <span className="text-[7px] opacity-70 truncate w-full text-center px-0.5">
                        {(ad.day_name || '').slice(0, 6)}
                      </span>
                    </>
                  ) : '—'}
                </button>
              )
            })}
          </div>
        </GlassCard>

        {/* Список дней */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
              Дни тренировок ({days.length})
            </span>
            <button onClick={() => { setNewDayName(''); setNewDayWeekday(null); setShowAddDay(true) }}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-xs font-medium"
              style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}>
              <Plus size={12} /> Добавить
            </button>
          </div>

          {days.map((day) => {
            const tpl = getTemplate(day.template_id)
            return (
              <GlassCard key={day.id}>
                <div className="flex items-start gap-3">
                  <div className="flex flex-col items-center gap-1 shrink-0">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold"
                      style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}>
                      {day.day_number}
                    </div>
                    {day.weekday != null ? (
                      <span className="px-2 py-0.5 rounded-lg text-[10px] font-bold"
                        style={{ background: 'rgba(251,146,60,0.2)', color: '#fb923c' }}>
                        {WEEKDAYS[day.weekday]}
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-lg text-[10px]"
                        style={{ background: 'rgba(255,255,255,0.04)', color: 'var(--app-hint)' }}>—</span>
                    )}
                  </div>
                  <div className="flex-1 min-w-0" onClick={() => openEdit(day)} style={{ cursor: 'pointer' }}>
                    <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                      {day.day_name || `День ${day.day_number}`}
                    </span>
                    {tpl?.exercises?.length ? (
                      <div className="mt-1.5 space-y-0.5">
                        {tpl.exercises.slice(0, 3).map((ex: any, idx: number) => (
                          <div key={idx} className="flex items-center gap-1.5 text-[10px]" style={{ color: 'var(--app-hint)' }}>
                            <Dumbbell size={10} style={{ color: '#818cf8' }} />
                            <span className="truncate">{ex.exercise_name}</span>
                            <span className="shrink-0" style={{ color: 'rgba(255,255,255,0.25)' }}>
                              {ex.sets}×{ex.reps || '—'}
                            </span>
                          </div>
                        ))}
                        {tpl.exercises.length > 3 && (
                          <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                            +{tpl.exercises.length - 3} ещё
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="text-[10px] mt-1" style={{ color: 'var(--app-hint)' }}>
                        Нет упражнений — нажмите для настройки
                      </div>
                    )}
                  </div>
                  <div className="flex flex-col items-center gap-1 shrink-0">
                    <button onClick={() => openEdit(day)} className="p-1.5 rounded-lg"
                      style={{ background: 'rgba(99,102,241,0.1)' }}>
                      <Edit3 size={14} style={{ color: '#a5b4fc' }} />
                    </button>
                    <button onClick={() => handleDeleteDay(day.id)} className="p-1.5 rounded-lg"
                      style={{ background: 'rgba(239,68,68,0.1)' }}>
                      <Trash2 size={14} style={{ color: '#ef4444' }} />
                    </button>
                  </div>
                </div>
              </GlassCard>
            )
          })}

          {days.length === 0 && (
            <div className="text-center py-6 text-sm" style={{ color: 'var(--app-hint)' }}>
              Нет дней. Добавьте первый день тренировки.
            </div>
          )}
        </div>
      </div>

      {/* ── Toast ── */}
      <AnimatePresence>
        {toast && (
          <motion.div className="fixed top-4 left-1/2 -translate-x-1/2 z-[60] px-4 py-2 rounded-xl text-sm font-medium"
            style={{ background: 'rgba(34,197,94,0.95)', color: 'white' }}
            initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
            {toast}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ═══ МОДАЛ РЕДАКТИРОВАНИЯ ДНЯ ═══ */}
      <AnimatePresence>
        {editingDay && (
          <>
            {/* Затемнённый фон */}
            <motion.div className="fixed inset-0 z-50" style={{ background: 'rgba(0,0,0,0.7)' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setEditingDay(null)} />
            {/* Панель снизу — ПЛОТНЫЙ ФОН */}
            <motion.div
              className="fixed bottom-0 left-0 right-0 z-[51] rounded-t-[24px] p-4 space-y-3 max-h-[90vh] overflow-y-auto"
              style={{ background: '#1a1a2e', borderTop: '1px solid rgba(255,255,255,0.1)' }}
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}>

              {/* Ручка */}
              <div className="flex justify-center">
                <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.2)' }} />
              </div>

              <h3 className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
                День {editingDay.day_number} · {editName || 'Без названия'}
              </h3>

              {/* Название */}
              <div>
                <label className="text-[11px] font-medium mb-1 block" style={{ color: 'var(--app-hint)' }}>Название</label>
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)}
                  placeholder="Грудь + Трицепс"
                  className="w-full px-3 py-2.5 rounded-xl text-sm bg-transparent outline-none"
                  style={{ color: 'var(--app-text)', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.03)' }} />
              </div>

              {/* День недели */}
              <div>
                <label className="text-[11px] font-medium mb-1 block" style={{ color: 'var(--app-hint)' }}>
                  День недели {editWeekday != null && <span style={{ color: '#fb923c' }}>· {WEEKDAYS[editWeekday]}</span>}
                </label>
                <div className="grid grid-cols-7 gap-1">
                  {WEEKDAYS.map((name, idx) => {
                    const occupied = days.find(d => d.weekday === idx && d.id !== editingDay.id)
                    const selected = editWeekday === idx
                    return (
                      <button key={idx}
                        onClick={() => setEditWeekday(selected ? null : idx)}
                        disabled={!!occupied}
                        className="py-2 rounded-xl text-[11px] font-bold transition-all"
                        style={{
                          background: selected ? 'rgba(251,146,60,0.3)' : 'rgba(255,255,255,0.04)',
                          border: selected ? '1.5px solid rgba(251,146,60,0.5)' : '1px solid rgba(255,255,255,0.06)',
                          color: selected ? '#fb923c' : occupied ? 'rgba(255,255,255,0.12)' : 'var(--app-text)',
                          opacity: occupied ? 0.3 : 1,
                        }}>
                        {name}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* ── Время тренировки ── */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <span style={{ color: 'var(--app-text)', fontSize: 13, fontWeight: 500 }}>
                    ⏰ Время тренировки
                  </span>
                  {editStartTime && editEndTime && (
                    <span style={{ color: '#fb923c', fontSize: 12 }}>· {editStartTime}–{editEndTime}</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {/* Время начала */}
                  <input
                    type="text" inputMode="numeric" placeholder="09:00" maxLength={5}
                    value={editStartTime}
                    onChange={e => {
                      let v = e.target.value.replace(/[^0-9:]/g, '')
                      if (v.length === 2 && !v.includes(':') && editStartTime.length < 3) v += ':'
                      if (v.length <= 5) setEditStartTime(v)
                    }}
                    style={{
                      flex: 1, padding: '8px 10px', borderRadius: 10,
                      background: 'rgba(30,30,50,0.8)', color: 'var(--app-text)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      fontSize: 14, textAlign: 'center' as const,
                    }}
                  />
                  <span style={{ color: 'var(--app-hint)', fontSize: 13 }}>—</span>
                  {/* Время окончания */}
                  <input
                    type="text" inputMode="numeric" placeholder="09:00" maxLength={5}
                    value={editEndTime}
                    onChange={e => {
                      let v = e.target.value.replace(/[^0-9:]/g, '')
                      if (v.length === 2 && !v.includes(':') && editEndTime.length < 3) v += ':'
                      if (v.length <= 5) setEditEndTime(v)
                    }}
                    style={{
                      flex: 1, padding: '8px 10px', borderRadius: 10,
                      background: 'rgba(30,30,50,0.8)', color: 'var(--app-text)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      fontSize: 14,
                    }}
                  />
                  {/* Кнопка сброса */}
                  {(editStartTime || editEndTime) && (
                    <button
                      onClick={() => { setEditStartTime(''); setEditEndTime('') }}
                      style={{
                        padding: '6px 10px', borderRadius: 8,
                        background: 'rgba(239,68,68,0.2)', color: '#ef4444',
                        border: 'none', fontSize: 12, cursor: 'pointer',
                      }}
                    >
                      ✕
                    </button>
                  )}
                </div>
                {!editStartTime && !editEndTime && (
                  <p style={{ color: 'var(--app-hint)', fontSize: 11, marginTop: 4 }}>
                    Без времени — тренировка на весь день
                  </p>
                )}
              </div>

              {/* ── Упражнения ── */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-[11px] font-medium" style={{ color: 'var(--app-hint)' }}>
                    Упражнения ({editExercises.length})
                  </label>
                  <div className="flex gap-1.5">
                    {/* Загрузить из шаблона */}
                    <button onClick={() => setShowTemplateSelect(!showTemplateSelect)}
                      className="px-2 py-1 rounded-lg text-[10px] font-medium"
                      style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}>
                      Из шаблона
                    </button>
                    {/* Добавить упражнение */}
                    <button onClick={() => { setShowExSearch(true); setExSearchQuery('') }}
                      className="px-2 py-1 rounded-lg text-[10px] font-medium"
                      style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}>
                      <Plus size={10} className="inline" /> Добавить
                    </button>
                  </div>
                </div>

                {/* Список шаблонов (dropdown) */}
                {showTemplateSelect && templates && (
                  <div className="mb-2 rounded-xl overflow-hidden border border-white/[0.06]"
                    style={{ background: 'rgba(0,0,0,0.4)', maxHeight: 150, overflowY: 'auto' }}>
                    {templates.map((tpl: any) => (
                      <button key={tpl.id}
                        onClick={() => loadFromTemplate(tpl.id)}
                        className="w-full text-left px-3 py-2 text-xs border-b border-white/[0.04] flex justify-between"
                        style={{ color: 'var(--app-text)' }}>
                        <span>{tpl.name}</span>
                        <span style={{ color: 'var(--app-hint)' }}>{tpl.exercises?.length || 0} упр.</span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Поиск упражнений */}
                <AnimatePresence>
                  {showExSearch && (
                    <motion.div className="mb-2 space-y-1.5"
                      initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}>
                      <div className="flex items-center gap-2 px-3 py-2 rounded-xl"
                        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
                        <Search size={14} style={{ color: 'var(--app-hint)' }} />
                        <input type="text" value={exSearchQuery}
                          onChange={(e) => setExSearchQuery(e.target.value)}
                          placeholder="Поиск упражнения..."
                          autoFocus
                          className="flex-1 text-xs bg-transparent outline-none"
                          style={{ color: 'var(--app-text)' }} />
                        <button onClick={() => setShowExSearch(false)} className="text-[10px]"
                          style={{ color: 'var(--app-hint)' }}>✕</button>
                      </div>
                      {searchResults && searchResults.length > 0 && (
                        <div className="rounded-xl overflow-hidden border border-white/[0.06]"
                          style={{ background: 'rgba(0,0,0,0.4)', maxHeight: 120, overflowY: 'auto' }}>
                          {searchResults.slice(0, 8).map((ex: any) => (
                            <button key={ex.id} onClick={() => addExercise(ex)}
                              className="w-full text-left px-3 py-2 text-[11px] border-b border-white/[0.04] flex justify-between"
                              style={{ color: 'var(--app-text)' }}>
                              <span>{ex.name}</span>
                              <span style={{ color: 'var(--app-hint)' }}>{ex.muscle_group}</span>
                            </button>
                          ))}
                        </div>
                      )}
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Список упражнений дня */}
                <div className="space-y-1.5">
                  {editExercises.map((ex, idx) => (
                    <div key={idx} className="flex items-center gap-2 p-2 rounded-xl"
                      style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.05)' }}>
                      <GripVertical size={12} style={{ color: 'rgba(255,255,255,0.15)' }} />
                      <div className="flex-1 min-w-0">
                        <div className="text-[11px] font-medium truncate" style={{ color: 'var(--app-text)' }}>
                          {ex.exercise_name}
                        </div>
                        {/* Параметры: подходы × повторы, вес */}
                        <div className="flex items-center gap-2 mt-1">
                          <div className="flex items-center gap-0.5">
                            <input type="number" value={ex.sets}
                              onChange={(e) => updateExercise(idx, 'sets', Number(e.target.value) || 1)}
                              className="w-8 text-center text-[10px] py-0.5 rounded bg-transparent outline-none"
                              style={{ color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.2)' }} />
                            <span className="text-[9px]" style={{ color: 'var(--app-hint)' }}>×</span>
                            <input type="number" value={ex.reps || ''}
                              onChange={(e) => updateExercise(idx, 'reps', Number(e.target.value) || null)}
                              placeholder="—"
                              className="w-8 text-center text-[10px] py-0.5 rounded bg-transparent outline-none"
                              style={{ color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.2)' }} />
                          </div>
                          <div className="flex items-center gap-0.5">
                            <input type="number" value={ex.weight_kg || ''}
                              onChange={(e) => updateExercise(idx, 'weight_kg', Number(e.target.value) || null)}
                              placeholder="—"
                              className="w-10 text-center text-[10px] py-0.5 rounded bg-transparent outline-none"
                              style={{ color: '#fb923c', border: '1px solid rgba(251,146,60,0.2)' }} />
                            <span className="text-[9px]" style={{ color: 'var(--app-hint)' }}>кг</span>
                          </div>
                        </div>
                      </div>
                      <button onClick={() => removeExercise(idx)} className="p-1 shrink-0">
                        <Trash2 size={12} style={{ color: '#ef4444' }} />
                      </button>
                    </div>
                  ))}
                  {editExercises.length === 0 && (
                    <div className="text-center py-3 text-[11px]" style={{ color: 'var(--app-hint)' }}>
                      Нет упражнений. Добавьте из каталога или загрузите шаблон.
                    </div>
                  )}
                </div>
              </div>

              {/* Кнопки */}
              <div className="flex gap-3 pb-2">
                <button onClick={() => setEditingDay(null)}
                  className="flex-1 py-3 rounded-xl text-sm font-medium"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-text)' }}>
                  Отмена
                </button>
                <button onClick={handleSaveDay} disabled={saving}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', opacity: saving ? 0.6 : 1 }}>
                  <Save size={16} />
                  {saving ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ═══ МОДАЛ ДОБАВЛЕНИЯ ДНЯ ═══ */}
      <AnimatePresence>
        {showAddDay && (
          <>
            <motion.div className="fixed inset-0 z-50" style={{ background: 'rgba(0,0,0,0.7)' }}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setShowAddDay(false)} />
            <motion.div
              className="fixed bottom-0 left-0 right-0 z-[51] rounded-t-[24px] p-4 space-y-4"
              style={{ background: '#1a1a2e', borderTop: '1px solid rgba(255,255,255,0.1)' }}
              initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 300 }}>
              <div className="flex justify-center">
                <div className="w-10 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.2)' }} />
              </div>
              <h3 className="text-base font-bold" style={{ color: 'var(--app-text)' }}>
                Новый день тренировки
              </h3>
              <input type="text" value={newDayName} onChange={(e) => setNewDayName(e.target.value)}
                placeholder="Название (напр. Грудь + Трицепс)..." autoFocus
                className="w-full px-3 py-2.5 rounded-xl text-sm bg-transparent outline-none"
                style={{ color: 'var(--app-text)', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(255,255,255,0.03)' }} />
              <div>
                <p className="text-[11px] font-medium mb-1.5" style={{ color: 'var(--app-hint)' }}>
                  День недели {newDayWeekday != null && <span style={{ color: '#fb923c' }}>· {WEEKDAYS[newDayWeekday]}</span>}
                </p>
                <div className="grid grid-cols-7 gap-1">
                  {WEEKDAYS.map((name, idx) => {
                    const occupied = days.find(d => d.weekday === idx)
                    return (
                      <button key={idx}
                        onClick={() => setNewDayWeekday(newDayWeekday === idx ? null : idx)}
                        disabled={!!occupied}
                        className="py-2 rounded-xl text-[11px] font-bold transition-colors"
                        style={{
                          background: newDayWeekday === idx ? 'rgba(251,146,60,0.25)' : 'rgba(255,255,255,0.04)',
                          border: newDayWeekday === idx ? '1px solid rgba(251,146,60,0.4)' : '1px solid rgba(255,255,255,0.06)',
                          color: newDayWeekday === idx ? '#fb923c' : occupied ? 'rgba(255,255,255,0.12)' : 'var(--app-text)',
                          opacity: occupied ? 0.3 : 1,
                        }}>
                        {name}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setShowAddDay(false)}
                  className="flex-1 py-3 rounded-xl text-sm font-medium"
                  style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--app-text)' }}>
                  Отмена
                </button>
                <button onClick={handleAddDay} disabled={!newDayName.trim() || saving}
                  className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold text-white"
                  style={{
                    background: newDayName.trim() ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'rgba(255,255,255,0.1)',
                    opacity: saving ? 0.6 : 1,
                  }}>
                  <Plus size={16} />
                  {saving ? 'Добавление...' : 'Добавить'}
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
