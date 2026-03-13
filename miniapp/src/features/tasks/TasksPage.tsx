/**
 * Главная страница задач.
 * Мультиселект: тап по кружку → выделение задачи → bulk-action бар.
 * Редактирование: свайп вправо → Edit → шит с заполненной формой.
 */
import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2, CheckCircle2, X } from 'lucide-react'
import type { TaskPeriod, Task, CreateTaskDto } from '../../api/tasks'
import { useTasksQuery, useCreateTask, usePatchTask, useDeleteTask } from '../../api/tasks'
import { ProgressHeader } from './ProgressHeader'
import { FilterTabs } from './FilterTabs'
import { TaskList } from './TaskList'
import { TaskCreateSheet } from './TaskCreateSheet'
import { FAB } from '../../shared/components/FAB'
import { TaskSkeletonLoader } from '../../shared/components/Loader'
import { useTelegram } from '../../shared/hooks/useTelegram'

const NAV_HEIGHT = 80

export function TasksPage() {
  const [period, setPeriod] = useState<TaskPeriod>('all')

  // Sheet состояние: null = закрыт, undefined = создание, Task = редактирование
  const [sheetTask, setSheetTask] = useState<Task | null | undefined>(undefined)
  const sheetOpen = sheetTask !== undefined

  // Мультиселект
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const selectionMode = selectedIds.size > 0

  const { user, haptic } = useTelegram()

  const { data: tasks = [], isLoading } = useTasksQuery(period)
  const { data: allTasks = [] }         = useTasksQuery('all')

  const createTask = useCreateTask()
  const patchTask  = usePatchTask()
  const deleteTask = useDeleteTask()

  // ── Одиночные действия ─────────────────────────────────────────────────────

  const handleDone = useCallback((id: number, isDone: boolean) => {
    haptic?.impactOccurred('light')
    patchTask.mutate({ id, is_done: isDone })
  }, [haptic, patchTask])

  const handleDelete = useCallback((id: number) => {
    haptic?.notificationOccurred('success')
    deleteTask.mutate(id)
    // Снимаем выделение если удалили выбранную
    setSelectedIds((prev) => { const next = new Set(prev); next.delete(id); return next })
  }, [haptic, deleteTask])

  const handleCreate = useCallback((dto: CreateTaskDto) => {
    haptic?.impactOccurred('medium')
    createTask.mutate(dto)
  }, [haptic, createTask])

  const handleUpdate = useCallback((id: number, dto: CreateTaskDto) => {
    haptic?.impactOccurred('medium')
    patchTask.mutate({ id, ...dto })
  }, [haptic, patchTask])

  // ── Мультиселект ───────────────────────────────────────────────────────────

  const handleSelect = useCallback((id: number) => {
    haptic?.impactOccurred('light')
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [haptic])

  const clearSelection = useCallback(() => setSelectedIds(new Set()), [])

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(tasks.map((t) => t.id)))
  }, [tasks])

  // ── Bulk-действия ──────────────────────────────────────────────────────────

  const bulkMarkDone = useCallback(() => {
    haptic?.notificationOccurred('success')
    selectedIds.forEach((id) => patchTask.mutate({ id, is_done: true }))
    clearSelection()
  }, [selectedIds, patchTask, haptic, clearSelection])

  const bulkDelete = useCallback(() => {
    haptic?.notificationOccurred('warning')
    selectedIds.forEach((id) => deleteTask.mutate(id))
    clearSelection()
  }, [selectedIds, deleteTask, haptic, clearSelection])

  // ── Sheet helpers ──────────────────────────────────────────────────────────

  const openCreate = () => setSheetTask(null)          // null = создание
  const openEdit   = (task: Task) => setSheetTask(task) // Task = редактирование
  const closeSheet = () => setSheetTask(undefined)      // undefined = закрыт

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--app-bg)' }}>
      {/* Декоративные блобы */}
      <div className="fixed top-0 right-0 w-64 h-64 rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)', transform: 'translate(30%, -30%)', zIndex: 0 }} />
      <div className="fixed bottom-32 left-0 w-48 h-48 rounded-full pointer-events-none"
        style={{ background: 'radial-gradient(circle, rgba(139,92,246,0.08) 0%, transparent 70%)', transform: 'translate(-30%, 30%)', zIndex: 0 }} />

      {/* Контент */}
      <div className="relative flex-1 overflow-y-auto" style={{ zIndex: 1, paddingBottom: 120 }}>
        <ProgressHeader tasks={allTasks} userName={user?.first_name} />
        <FilterTabs active={period} onChange={setPeriod} />

        {/* Заголовок мультиселекта */}
        <AnimatePresence>
          {selectionMode && (
            <motion.div
              className="flex items-center justify-between px-4 py-2 mx-4 mt-2 rounded-[14px]"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)' }}
              initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            >
              <span className="text-sm font-medium" style={{ color: '#818cf8' }}>
                Выбрано: {selectedIds.size}
              </span>
              <div className="flex gap-2">
                <button onClick={selectAll} className="text-xs px-2 py-1 rounded-[8px]"
                  style={{ background: 'rgba(99,102,241,0.2)', color: '#818cf8' }}>
                  Все
                </button>
                <button onClick={clearSelection} className="text-xs px-2 py-1 rounded-[8px]"
                  style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--app-hint)' }}>
                  Отмена
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="mt-2">
          {isLoading ? (
            <TaskSkeletonLoader />
          ) : (
            <TaskList
              tasks={tasks}
              onDone={handleDone}
              onDelete={handleDelete}
              onEdit={openEdit}
              onSelect={handleSelect}
              selectedIds={selectedIds}
              selectionMode={selectionMode}
              period={period}
            />
          )}
        </div>
      </div>

      {/* FAB — скрываем в режиме селекта */}
      <AnimatePresence>
        {!selectionMode && (
          <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }}>
            <FAB onClick={openCreate} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Bulk-action бар (поверх BottomNav) ── */}
      <AnimatePresence>
        {selectionMode && (
          <motion.div
            className="fixed left-0 right-0 z-40 px-4 pb-3 pt-2"
            style={{ bottom: NAV_HEIGHT }}
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 400, damping: 32 }}
          >
            <div
              className="flex gap-3 rounded-[20px] p-3"
              style={{ background: 'rgba(15,15,26,0.95)', border: '1px solid rgba(255,255,255,0.1)', backdropFilter: 'blur(20px)' }}
            >
              {/* Отмена выбора */}
              <button
                onClick={clearSelection}
                className="w-10 h-10 rounded-[12px] flex items-center justify-center flex-shrink-0"
                style={{ background: 'rgba(255,255,255,0.08)' }}
              >
                <X size={18} style={{ color: 'var(--app-hint)' }} />
              </button>

              {/* Отметить выполненными */}
              <button
                onClick={bulkMarkDone}
                className="flex-1 h-10 rounded-[12px] flex items-center justify-center gap-2"
                style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.2), rgba(22,163,74,0.2))', border: '1px solid rgba(34,197,94,0.3)' }}
              >
                <CheckCircle2 size={16} style={{ color: '#22c55e' }} />
                <span className="text-sm font-medium" style={{ color: '#22c55e' }}>Выполнено</span>
              </button>

              {/* Удалить выбранные */}
              <button
                onClick={bulkDelete}
                className="flex-1 h-10 rounded-[12px] flex items-center justify-center gap-2"
                style={{ background: 'linear-gradient(135deg, rgba(239,68,68,0.2), rgba(220,38,38,0.2))', border: '1px solid rgba(239,68,68,0.3)' }}
              >
                <Trash2 size={16} style={{ color: '#ef4444' }} />
                <span className="text-sm font-medium" style={{ color: '#ef4444' }}>Удалить</span>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sheet создания / редактирования */}
      <TaskCreateSheet
        open={sheetOpen}
        onClose={closeSheet}
        onCreate={handleCreate}
        onUpdate={handleUpdate}
        editTask={sheetTask}
        isLoading={createTask.isPending || patchTask.isPending}
      />
    </div>
  )
}
