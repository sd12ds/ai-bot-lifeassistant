/**
 * Карточка задачи с тремя действиями:
 * - Круг слева     → мультиселект (onSelect)
 * - Свайп влево    → удалить (красный фон)
 * - Свайп вправо   → снэп-открытие панели Done + Edit (зелёный/синий)
 * Также отображает временной интервал start_at → end_at если задан.
 */
import { useState } from 'react'
import { motion, useMotionValue, useTransform, animate } from 'framer-motion'
import { Check, Trash2, Clock, Pencil, CheckCircle2, CalendarRange, Repeat } from 'lucide-react'
import { formatDistanceToNow, isPast, isSameDay, format } from 'date-fns'
import { ru } from 'date-fns/locale'
import type { Task } from '../../api/tasks'
import { TagPill } from '../../shared/ui/TagPill'
import { PriorityBadge } from '../../shared/ui/PriorityBadge'

// Ширина открытой правой панели (Done + Edit)
const RIGHT_PANEL_W = 130

interface TaskCardProps {
  task: Task
  onDone: (id: number, isDone: boolean) => void
  onDelete: (id: number) => void
  onEdit: (task: Task) => void
  selected: boolean
  selectionMode: boolean
  onSelect: (id: number) => void
}

export function TaskCard({
  task, onDone, onDelete, onEdit,
  selected, selectionMode, onSelect,
}: TaskCardProps) {
  const [deleted, setDeleted] = useState(false)
  const [rightOpen, setRightOpen] = useState(false)
  const x = useMotionValue(0)

  // Прозрачность левой (delete) панели
  const deleteOpacity  = useTransform(x, [-100, -30], [1, 0])
  // Прозрачность правой (done+edit) панели
  const actionsOpacity = useTransform(x, [20, 80], [0, 1])
  // Затемнение самой карточки при свайпе
  const cardOpacity    = useTransform(x, [-100, -60, 0, 60, 100], [0.4, 0.8, 1, 0.8, 0.4])

  const snapClose = () => {
    setRightOpen(false)
    animate(x, 0, { type: 'spring', stiffness: 400, damping: 35 })
  }

  const snapOpen = () => {
    setRightOpen(true)
    animate(x, RIGHT_PANEL_W, { type: 'spring', stiffness: 400, damping: 35 })
  }

  const handleDragEnd = (_: unknown, info: { offset: { x: number }; velocity: { x: number } }) => {
    const ox = info.offset.x
    if (ox < -80) {
      // Свайп влево → удалить
      setDeleted(true)
      animate(x, -300, { duration: 0.2 })
      setTimeout(() => onDelete(task.id), 200)
    } else if (ox > 60 || info.velocity.x > 500) {
      // Свайп вправо → открыть панель действий
      snapOpen()
    } else {
      // Вернуть на место
      snapClose()
    }
  }

  const handleDone = () => {
    snapClose()
    setTimeout(() => onDone(task.id, !task.is_done), 150)
  }

  const handleEdit = () => {
    snapClose()
    setTimeout(() => onEdit(task), 150)
  }

  // Форматируем дедлайн: полная дата + время + оставшееся время
  const dueLabel = (() => {
    if (!task.due_datetime) return null
    try {
      const dt = new Date(task.due_datetime)
      const overdue = isPast(dt) && !task.is_done
      // Полная дата: "11 мар, 15:00"
      const dateStr = format(dt, 'd MMM, HH:mm', { locale: ru })
      // Оставшееся время: "через 2 часа" или "3 часа назад"
      const relStr = formatDistanceToNow(dt, { addSuffix: true, locale: ru })
      return { dateStr, relStr, overdue }
    } catch { return null }
  })()

  // Форматируем временной интервал (start_at → end_at) с полной датой
  const intervalLabel = (() => {
    if (!task.start_at) return null
    try {
      const start = new Date(task.start_at)
      // Полная дата начала: "11 мар, 14:00"
      const startFull = format(start, 'd MMM, HH:mm', { locale: ru })
      // Оставшееся время до начала
      const overdue = isPast(start) && !task.is_done
      const relStr = formatDistanceToNow(start, { addSuffix: true, locale: ru })

      if (!task.end_at) return { dateStr: startFull, relStr, overdue }

      const end = new Date(task.end_at)
      const endTime = format(end, 'HH:mm')

      // Если один день — "11 мар, 14:00–15:00"; если разные — "11 мар, 14:00 → 12 мар, 10:00"
      const dateStr = isSameDay(start, end)
        ? `${startFull}–${endTime}`
        : `${startFull} → ${format(end, 'd MMM, HH:mm', { locale: ru })}`
      return { dateStr, relStr, overdue }
    } catch { return null }
  })()

  return (
    <motion.div
      className="relative mx-4"
      initial={{ opacity: 0, y: 12 }}
      animate={deleted ? { opacity: 0, height: 0, marginBottom: 0 } : { opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
    >
      {/* ── Фон: левая (delete) панель ── */}
      <motion.div
        className="absolute inset-0 rounded-[20px] flex items-center justify-end pr-5"
        style={{ background: 'linear-gradient(135deg, #ef4444, #dc2626)', opacity: deleteOpacity, pointerEvents: 'none' }}
      >
        <Trash2 size={22} color="white" />
      </motion.div>

      {/* ── Фон: правая (done + edit) панель ──
          pointerEvents: 'none' на контейнере — не блокирует drag.
          Кнопки активны только когда панель реально открыта. ── */}
      <motion.div
        className="absolute inset-0 rounded-[20px] flex items-center justify-start pl-3 gap-2"
        style={{ opacity: actionsOpacity, pointerEvents: 'none' }}
      >
        {/* Edit — синяя кнопка */}
        <button
          onPointerUp={(e) => { e.stopPropagation(); handleEdit() }}
          style={{
            pointerEvents: rightOpen ? 'auto' : 'none',
            background: 'linear-gradient(135deg, #6366f1, #818cf8)',
          }}
          className="w-14 h-14 rounded-[16px] flex flex-col items-center justify-center gap-0.5"
        >
          <Pencil size={18} color="white" />
          <span className="text-[10px] text-white font-medium">Изменить</span>
        </button>

        {/* Done — зелёная кнопка */}
        <button
          onPointerUp={(e) => { e.stopPropagation(); handleDone() }}
          style={{
            pointerEvents: rightOpen ? 'auto' : 'none',
            background: task.is_done
              ? 'linear-gradient(135deg, #64748b, #475569)'
              : 'linear-gradient(135deg, #22c55e, #16a34a)',
          }}
          className="w-14 h-14 rounded-[16px] flex flex-col items-center justify-center gap-0.5"
        >
          <CheckCircle2 size={18} color="white" />
          <span className="text-[10px] text-white font-medium">
            {task.is_done ? 'Отменить' : 'Готово'}
          </span>
        </button>
      </motion.div>

      {/* ── Основная карточка ── */}
      <motion.div
        drag="x"
        dragConstraints={{ left: -120, right: RIGHT_PANEL_W }}
        dragElastic={{ left: 0.1, right: 0.1 }}
        onDragEnd={handleDragEnd}
        style={{
          x,
          opacity: cardOpacity,
          background: selected
            ? 'linear-gradient(135deg, rgba(99,102,241,0.18), rgba(139,92,246,0.12))'
            : 'var(--glass-bg)',
          boxShadow: selected
            ? '0 0 0 2px #6366f1, var(--shadow-card)'
            : 'var(--shadow-card)',
          position: 'relative',
          zIndex: 1,
        }}
        className="rounded-[20px] p-4 pl-5 border backdrop-blur-xl overflow-hidden"
        onClick={rightOpen ? snapClose : undefined}
      >
        {/* Цветная полоска приоритета слева */}
        <PriorityBadge priority={task.priority as 1 | 2 | 3} />

        <div className="flex items-start gap-3">
          {/* ── Круг: мультиселект / маркер выполнения ── */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onSelect(task.id)
            }}
            className="flex-shrink-0 mt-0.5 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all"
            style={{
              borderColor: selected
                ? '#6366f1'
                : selectionMode
                ? 'rgba(255,255,255,0.35)'
                : task.is_done
                ? '#818cf8'
                : 'rgba(255,255,255,0.2)',
              background: selected
                ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                : task.is_done && !selectionMode
                ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                : 'transparent',
            }}
          >
            {selected && <Check size={13} color="white" strokeWidth={3} />}
            {!selected && task.is_done && !selectionMode && (
              <Check size={13} color="white" strokeWidth={3} />
            )}
          </button>

          {/* Контент */}
          <div className="flex-1 min-w-0">
            <p
              className="text-sm font-semibold leading-snug"
              style={{
                color: task.is_done ? 'var(--app-hint)' : 'var(--app-text)',
                textDecoration: task.is_done ? 'line-through' : 'none',
              }}
            >
              {task.title}
            </p>

            {/* Временной интервал (start_at → end_at) */}
            {intervalLabel && (
              <div className="flex items-center gap-1 mt-1 flex-wrap">
                <CalendarRange size={11} style={{ color: '#818cf8' }} />
                <span className="text-xs font-medium" style={{ color: '#818cf8' }}>
                  {intervalLabel.dateStr}
                </span>
                <span className="text-xs" style={{ color: intervalLabel.overdue ? '#ef4444' : 'var(--app-hint)' }}>
                  · {intervalLabel.relStr}
                </span>
              </div>
            )}

            {/* Иконка повтора для экземпляров повторяющихся задач */}
            {task.parent_task_id && (
              <div className="flex items-center gap-1 mt-1">
                <Repeat size={11} style={{ color: '#a78bfa' }} />
                <span className="text-xs font-medium" style={{ color: '#a78bfa' }}>
                  Повторяется
                </span>
              </div>
            )}

            {/* Дедлайн: скрываем целиком если intervalLabel уже показывает время */}
            {dueLabel && !intervalLabel && (
              <div className="flex items-center gap-1 mt-1 flex-wrap">
                <Clock size={11} style={{ color: dueLabel.overdue ? '#ef4444' : 'var(--app-hint)' }} />
                <span className="text-xs font-medium" style={{ color: dueLabel.overdue ? '#ef4444' : 'var(--app-text)' }}>
                  {dueLabel.dateStr}
                </span>
                {/* Скрываем относительное время если intervalLabel уже показывает его */}
                {!intervalLabel && (
                  <span className="text-xs" style={{ color: dueLabel.overdue ? '#ef4444' : 'var(--app-hint)' }}>
                    · {dueLabel.relStr}
                  </span>
                )}
              </div>
            )}

            {task.tags?.filter(t => !/^program:\d+$/.test(t)).length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {task.tags.filter(t => !/^program:\d+$/.test(t)).slice(0, 3).map((tag) => (
                  <TagPill key={tag} label={tag} />
                ))}
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}
