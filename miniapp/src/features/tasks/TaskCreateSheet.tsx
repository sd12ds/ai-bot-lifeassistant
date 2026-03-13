/**
 * Bottom sheet для создания И редактирования задачи.
 * При передаче editTask — режим редактирования (форма заполнена, кнопка «Обновить»).
 * Поддерживает: дедлайн, временной интервал (от → до), приоритет, теги.
 */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Zap, Clock, Tag, Flag, CalendarRange, ChevronDown, Bell } from 'lucide-react'
import type { CreateTaskDto, PatchTaskDto, TaskPriority, Task } from '../../api/tasks'

interface TaskCreateSheetProps {
  open: boolean
  onClose: () => void
  onCreate: (dto: CreateTaskDto) => void
  onUpdate?: (id: number, dto: CreateTaskDto) => void
  editTask?: Task | null   // если задан — режим редактирования
  isLoading?: boolean
}

const PRIORITY_OPTIONS: { value: TaskPriority; label: string; color: string }[] = [
  { value: 1, label: '🔺 Высокий', color: '#ef4444' },
  { value: 2, label: '🔸 Обычный', color: '#f59e0b' },
  { value: 3, label: '🔹 Низкий',  color: '#22c55e' },
]

// Пресеты напоминаний: ключ = минуты до дедлайна (0 = в момент дедлайна, -1 = отключить, -2 = своё)
const REMIND_PRESETS: { label: string; minutes: number }[] = [
  { label: 'Нет',    minutes: -1 },
  { label: '5 мин', minutes: 5 },
  { label: '15 мин', minutes: 15 },
  { label: '30 мин', minutes: 30 },
  { label: '1 час',  minutes: 60 },
  { label: '2 час',  minutes: 120 },
  { label: '1 день',  minutes: 1440 },
  { label: 'Своё',   minutes: -2 },
]

const NAV_HEIGHT = 80

const inputStyle: React.CSSProperties = {
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.08)',
  color: 'var(--app-text)',
  fontSize: '16px',
  lineHeight: '1.4',
}

// Разбивает ISO datetime на дату и время для полей ввода
function splitIso(iso: string | null | undefined): { date: string; time: string } {
  if (!iso) return { date: '', time: '' }
  try {
    const dt = new Date(iso)
    const pad = (n: number) => n.toString().padStart(2, '0')
    const date = `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`
    const time = dt.toTimeString().slice(0, 5)
    return { date, time }
  } catch { return { date: '', time: '' } }
}

// Собирает ISO строку из date + time (или null если дата пустая)
function buildIso(date: string, time: string): string | null {
  if (!date) return null
  return new Date(date + 'T' + (time || '09:00')).toISOString()
}

export function TaskCreateSheet({
  open, onClose, onCreate, onUpdate, editTask, isLoading,
}: TaskCreateSheetProps) {
  const isEdit = !!editTask

  // Основные поля
  const [title, setTitle]         = useState('')
  const [dueDate, setDueDate]     = useState('')
  const [dueTime, setDueTime]     = useState('')
  const [priority, setPriority]   = useState<TaskPriority>(2)
  const [tagsInput, setTagsInput] = useState('')

  // Интервал (от → до)
  const [showInterval, setShowInterval] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endDate, setEndDate]     = useState('')
  const [endTime, setEndTime]     = useState('')

  // Напоминание: -1=откл, цифра=минуты до, -2=своё время
  const [remindPreset, setRemindPreset] = useState<number>(-1)
  const [remindCustom, setRemindCustom] = useState('')  // значение datetime-local

  // При открытии заполняем форму данными задачи (если редактирование)
  useEffect(() => {
    if (open && editTask) {
      setTitle(editTask.title)
      const due = splitIso(editTask.due_datetime)
      setDueDate(due.date)
      setDueTime(due.time)
      setPriority((editTask.priority as TaskPriority) || 2)
      setTagsInput((editTask.tags ?? []).join(', '))

      // Если у задачи есть интервал — раскрываем секцию
      if (editTask.start_at || editTask.end_at) {
        setShowInterval(true)
        const s = splitIso(editTask.start_at)
        const e = splitIso(editTask.end_at)
        setStartDate(s.date); setStartTime(s.time)
        setEndDate(e.date);   setEndTime(e.time)
      } else {
        setShowInterval(false)
        setStartDate(''); setStartTime(''); setEndDate(''); setEndTime('')
      }
    } else if (open && !editTask) {
      // Создание — чистая форма
      setTitle(''); setDueDate(''); setDueTime(''); setPriority(2); setTagsInput('')
      setShowInterval(false)
      setStartDate(''); setStartTime(''); setEndDate(''); setEndTime('')
      setRemindPreset(-1); setRemindCustom('')
    }
    // При открытии в режиме редактирования — восстанавливаем remind_at
    if (open && editTask?.remind_at) {
      setRemindPreset(-2)
      // Приводим ISO в datetime-local (YYYY-MM-DDTHH:mm)
      const d = new Date(editTask.remind_at)
      const pad = (n: number) => n.toString().padStart(2, '0')
      setRemindCustom(
        `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
      )
    } else if (open) {
      setRemindPreset(-1); setRemindCustom('')
    }
  }, [open, editTask])

  // Вычисляет remind_at: на основе пресета (вичет offset от due) или своего времени
  const buildRemindAt = (): string | null => {
    if (remindPreset === -1) return null          // Отключить
    if (remindPreset === -2) {                    // Своё время
      return remindCustom ? new Date(remindCustom).toISOString() : null
    }
    // Пресет: вычитаем due_datetime - offset
    const dueIso = buildIso(dueDate, dueTime)
    if (!dueIso) return null
    return new Date(new Date(dueIso).getTime() - remindPreset * 60_000).toISOString()
  }

  const buildDto = (): CreateTaskDto & PatchTaskDto => {
    const tags = tagsInput.split(',').map((t) => t.trim()).filter(Boolean)
    return {
      title: title.trim(),
      priority,
      due_datetime: buildIso(dueDate, dueTime),
      start_at: showInterval ? buildIso(startDate, startTime) : null,
      end_at:   showInterval ? buildIso(endDate, endTime)     : null,
      tags,
      remind_at: dueDate ? buildRemindAt() : null,  // отправляем только если есть дедлайн
    }
  }

  const handleSubmit = () => {
    if (!title.trim()) return
    if (isEdit && editTask && onUpdate) {
      onUpdate(editTask.id, buildDto())
    } else {
      onCreate(buildDto())
    }
    onClose()
  }

  // Сброс интервала при закрытии секции
  const toggleInterval = () => {
    if (showInterval) {
      setStartDate(''); setStartTime(''); setEndDate(''); setEndTime('')
    }
    setShowInterval((v) => !v)
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-50"
            style={{ background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)' }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />

          <motion.div
            className="fixed left-0 right-0 z-50 rounded-t-[28px] flex flex-col"
            style={{
              bottom: NAV_HEIGHT,
              maxHeight: `calc(92dvh - ${NAV_HEIGHT}px)`,
              background: 'var(--app-bg-section, #1a1a2e)',
              border: '1px solid var(--glass-border)',
              borderBottom: 'none',
            }}
            initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}
            drag="y" dragConstraints={{ top: 0, bottom: 0 }} dragElastic={{ top: 0, bottom: 0.3 }}
            onDragEnd={(_: unknown, info: { offset: { y: number } }) => {
              if (info.offset.y > 80) onClose()
            }}
          >
            {/* Шапка */}
            <div className="flex-shrink-0 px-6 pt-3 pb-2">
              <div className="flex justify-center mb-3">
                <div className="w-9 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.18)' }} />
              </div>
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                  {isEdit ? 'Редактировать задачу' : 'Новая задача'}
                </h2>
                <button
                  onClick={onClose}
                  className="w-8 h-8 rounded-full flex items-center justify-center"
                  style={{ background: 'rgba(255,255,255,0.08)' }}
                >
                  <X size={16} style={{ color: 'var(--app-hint)' }} />
                </button>
              </div>
            </div>

            {/* Форма */}
            <div className="flex-1 overflow-y-auto px-6 pb-5" style={{ overscrollBehavior: 'contain' }}>
              <div className="flex flex-col gap-3 pt-2">

                {/* Название */}
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Zap size={13} style={{ color: '#818cf8' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>Название задачи</span>
                  </div>
                  <input
                    type="text" value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Что нужно сделать?"
                    autoFocus
                    className="w-full px-4 py-3 rounded-[14px] outline-none"
                    style={inputStyle}
                    onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  />
                </div>

                {/* Дедлайн */}
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Clock size={13} style={{ color: '#818cf8' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>Дедлайн (необязательно)</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="date" value={dueDate}
                      onChange={(e) => setDueDate(e.target.value)}
                      className="flex-1 px-3 py-3 rounded-[14px] outline-none"
                      style={{ ...inputStyle, color: dueDate ? 'var(--app-text)' : 'var(--app-hint)', colorScheme: 'dark', minWidth: 0 }}
                    />
                    <input
                      type="time" value={dueTime}
                      onChange={(e) => setDueTime(e.target.value)}
                      
                      className="w-28 px-3 py-3 rounded-[14px] outline-none"
                      style={{ ...inputStyle, color: dueTime ? 'var(--app-text)' : 'var(--app-hint)', colorScheme: 'dark' }}
                    />
                  </div>
                  {dueDate && (
                    <button onClick={() => { setDueDate(''); setDueTime(''); setRemindPreset(-1); setRemindCustom('') }}
                      className="mt-1.5 text-xs" style={{ color: 'var(--app-hint)' }}>
                      × Убрать дедлайн
                    </button>
                  )}
                </div>

                {/* Напоминание — показываем только если задан дедлайн */}
                <AnimatePresence>
                  {dueDate && (
                    <motion.div
                      key="remind-block"
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      transition={{ duration: 0.2 }}
                      style={{ overflow: 'hidden' }}
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-2">
                          <Bell size={13} style={{ color: '#818cf8' }} />
                          <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                            Напоминание
                          </span>
                        </div>
                        {/* Сетка пресетов */}
                        <div className="flex flex-wrap gap-1.5">
                          {REMIND_PRESETS.map((p) => (
                            <button
                              key={p.minutes}
                              onClick={() => setRemindPreset(p.minutes)}
                              className="px-3 py-1.5 rounded-[10px] text-xs font-medium transition-all"
                              style={{
                                background: remindPreset === p.minutes
                                  ? 'rgba(99,102,241,0.25)'
                                  : 'rgba(255,255,255,0.05)',
                                border: `1px solid ${
                                  remindPreset === p.minutes
                                    ? '#6366f1'
                                    : 'rgba(255,255,255,0.08)'
                                }`,
                                color: remindPreset === p.minutes
                                  ? '#a5b4fc'
                                  : 'var(--app-hint)',
                              }}
                            >
                              {p.label}
                            </button>
                          ))}
                        </div>
                        {/* Своё время */}
                        <AnimatePresence>
                          {remindPreset === -2 && (
                            <motion.div
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              transition={{ duration: 0.18 }}
                              style={{ overflow: 'hidden' }}
                            >
                              <input
                                type="datetime-local"
                                value={remindCustom}
                                onChange={(e) => setRemindCustom(e.target.value)}
                                className="w-full mt-2 px-3 py-2.5 rounded-[12px] outline-none"
                                style={{ ...inputStyle, colorScheme: 'dark' }}
                              />
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* ── Интервал (от → до) ── */}
                <div>
                  {/* Toggle-заголовок */}
                  <button
                    onClick={toggleInterval}
                    className="flex items-center gap-2 w-full mb-1.5"
                  >
                    <CalendarRange size={13} style={{ color: showInterval ? '#818cf8' : 'var(--app-hint)' }} />
                    <span
                      className="text-xs font-medium flex-1 text-left"
                      style={{ color: showInterval ? '#818cf8' : 'var(--app-hint)' }}
                    >
                      Временной интервал
                    </span>
                    <motion.div
                      animate={{ rotate: showInterval ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <ChevronDown size={14} style={{ color: 'var(--app-hint)' }} />
                    </motion.div>
                  </button>

                  {/* Раскрывающаяся секция */}
                  <AnimatePresence>
                    {showInterval && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        transition={{ duration: 0.2 }}
                        style={{ overflow: 'hidden' }}
                      >
                        <div className="flex flex-col gap-2 pt-1">
                          {/* Начало */}
                          <div>
                            <span className="text-[11px] mb-1 block" style={{ color: 'var(--app-hint)' }}>
                              Начало
                            </span>
                            <div className="flex gap-2">
                              <input
                                type="date" value={startDate}
                                onChange={(e) => {
                                  setStartDate(e.target.value)
                                  // Автоподставляем дату конца если пустая
                                  if (!endDate) setEndDate(e.target.value)
                                }}
                                className="flex-1 px-3 py-2.5 rounded-[12px] outline-none"
                                style={{ ...inputStyle, colorScheme: 'dark', minWidth: 0 }}
                              />
                              <input
                                type="time" value={startTime}
                                onChange={(e) => setStartTime(e.target.value)}
                                
                                className="w-28 px-3 py-2.5 rounded-[12px] outline-none"
                                style={{ ...inputStyle, colorScheme: 'dark' }}
                              />
                            </div>
                          </div>

                          {/* Конец */}
                          <div>
                            <span className="text-[11px] mb-1 block" style={{ color: 'var(--app-hint)' }}>
                              Конец
                            </span>
                            <div className="flex gap-2">
                              <input
                                type="date" value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                className="flex-1 px-3 py-2.5 rounded-[12px] outline-none"
                                style={{ ...inputStyle, colorScheme: 'dark', minWidth: 0 }}
                              />
                              <input
                                type="time" value={endTime}
                                onChange={(e) => setEndTime(e.target.value)}
                                
                                className="w-28 px-3 py-2.5 rounded-[12px] outline-none"
                                style={{ ...inputStyle, colorScheme: 'dark' }}
                              />
                            </div>
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>

                {/* Приоритет */}
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Flag size={13} style={{ color: '#818cf8' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>Приоритет</span>
                  </div>
                  <div className="flex gap-2">
                    {PRIORITY_OPTIONS.map((opt) => (
                      <button key={opt.value} onClick={() => setPriority(opt.value)}
                        className="flex-1 py-2.5 rounded-[12px] text-xs font-medium transition-all"
                        style={{
                          background: priority === opt.value ? `${opt.color}22` : 'rgba(255,255,255,0.05)',
                          border: `1px solid ${priority === opt.value ? opt.color : 'rgba(255,255,255,0.08)'}`,
                          color: priority === opt.value ? opt.color : 'var(--app-hint)',
                        }}>
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Теги */}
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Tag size={13} style={{ color: '#818cf8' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>Теги (через запятую)</span>
                  </div>
                  <input
                    type="text" value={tagsInput}
                    onChange={(e) => setTagsInput(e.target.value)}
                    placeholder="работа, личное, срочно"
                    className="w-full px-4 py-3 rounded-[14px] outline-none"
                    style={inputStyle}
                  />
                </div>

                {/* Кнопка сохранить/обновить */}
                <button
                  onClick={handleSubmit}
                  disabled={!title.trim() || isLoading}
                  className="w-full py-4 rounded-[14px] font-semibold text-white transition-opacity mt-1"
                  style={{
                    fontSize: '16px',
                    background: title.trim() ? 'linear-gradient(135deg, #6366f1, #8b5cf6)' : 'rgba(255,255,255,0.1)',
                    opacity: isLoading ? 0.7 : 1,
                  }}
                >
                  {isLoading ? 'Сохраняем...' : isEdit ? '✓ Обновить задачу' : '✓ Сохранить задачу'}
                </button>

              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
