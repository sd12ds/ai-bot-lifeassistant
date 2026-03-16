/**
 * Страница программ тренировок.
 * Список программ, активная программа, AI-генерация,
 * детали программы с днями, секция шаблонов, кнопка начать тренировку.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Trash2, Sparkles, ChevronDown, ChevronUp,
  Play, Loader2, FileText, Dumbbell, Edit3,
} from 'lucide-react'
import {
  usePrograms, useActiveProgram, useNextWorkout,
  useGenerateProgram, useActivateProgram, useDeleteProgram,
  useTemplates, useApplyTemplate, useDeleteTemplate,
  type ProgramGenerateDto,
} from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'
import { Toast } from '../../shared/ui/Toast'

/** Метки целей */
const GOAL_LABELS: Record<string, { label: string; icon: string }> = {
  gain_muscle: { label: 'Набор массы', icon: '💪' },
  lose_weight: { label: 'Похудение', icon: '🔥' },
  maintain: { label: 'Поддержание', icon: '⚖️' },
  endurance: { label: 'Выносливость', icon: '🏃' },
  strength: { label: 'Сила', icon: '🏋️' },
  home_fitness: { label: 'Дом', icon: '🏠' },
  return_to_form: { label: 'Возвращение', icon: '🔄' },
}

/** Метки уровней */
const DIFF_LABELS: Record<string, string> = {
  beginner: 'Начинающий',
  intermediate: 'Средний',
  advanced: 'Продвинутый',
}

/** Метки локаций */
const LOC_LABELS: Record<string, string> = {
  gym: 'Зал',
  home: 'Дом',
  outdoor: 'Улица',
  mixed: 'Смешанное',
}

export function ProgramsPage() {
  const navigate = useNavigate()
  const { data: programs } = usePrograms()
  useActiveProgram()
  const { data: nextWorkout } = useNextWorkout()
  const generateMut = useGenerateProgram()
  const [toastMsg, setToastMsg] = useState('')
  const activateMut = useActivateProgram()
  const deleteMut = useDeleteProgram()

  // Шаблоны
  const { data: templates } = useTemplates()
  const applyTemplateMut = useApplyTemplate()
  const deleteTemplateMut = useDeleteTemplate()

  // Форма генерации
  const [showGenerate, setShowGenerate] = useState(false)
  const [genForm, setGenForm] = useState<ProgramGenerateDto>({
    goal_type: 'gain_muscle',
    difficulty: 'intermediate',
    location: 'gym',
    days_per_week: 3,
    duration_weeks: 4,
    notes: '',
  })

  // Раскрытые программы и шаблоны
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [expandedTemplateId, setExpandedTemplateId] = useState<number | null>(null)

  // Генерация программы
  const handleGenerate = async () => {
    try {
      await generateMut.mutateAsync(genForm)
      setShowGenerate(false)
      setToastMsg('Программа сгенерирована ✓')
      setTimeout(() => setToastMsg(''), 3000)
    } catch (e) {
      console.error('Ошибка генерации:', e)
      setToastMsg('Ошибка генерации')
      setTimeout(() => setToastMsg(''), 3000)
    }
  }

  // Применить шаблон — создаёт тренировку из шаблона и переходит на экран тренировки
  const handleApplyTemplate = async (templateId: number) => {
    try {
      await applyTemplateMut.mutateAsync(templateId)
      navigate('/fitness/workout')
    } catch (e) {
      console.error('Ошибка применения шаблона:', e)
    }
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/fitness')} className="p-2 -ml-2">
            <ArrowLeft size={22} style={{ color: 'var(--app-text)' }} />
          </button>
          <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>
            Программы
          </h1>
        </div>
        <button
          onClick={() => setShowGenerate(!showGenerate)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium"
          style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.2), rgba(139,92,246,0.15))', color: '#a5b4fc' }}
        >
          <Sparkles size={14} /> AI
        </button>
      </div>

      {/* Контент */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">
        {/* ── Следующая тренировка ── */}
        {nextWorkout && (
          <GlassCard
            className="cursor-pointer"
            onClick={() => navigate('/fitness/workout', { state: { fromProgram: true } })}
          >
            <div className="flex items-center gap-3">
              <div
                className="w-12 h-12 rounded-2xl flex items-center justify-center text-xl"
                style={{ background: 'linear-gradient(135deg, rgba(34,197,94,0.2), rgba(16,185,129,0.15))' }}
              >
                ▶️
              </div>
              <div className="flex-1">
                <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                  Следующая тренировка
                </div>
                <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                  {nextWorkout.program_name} · День {nextWorkout.day_number}/{nextWorkout.total_days}
                </div>
                <div className="text-xs mt-0.5 flex items-center gap-1.5" style={{ color: '#a5b4fc' }}>
                  {nextWorkout.weekday_name && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                      style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}>
                      {nextWorkout.weekday_name}
                    </span>
                  )}
                  {nextWorkout.day_name}
                </div>
              </div>
              <Play size={20} style={{ color: '#22c55e' }} />
            </div>
          </GlassCard>
        )}

        {/* ── Форма AI-генерации ── */}
        <AnimatePresence>
          {showGenerate && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
            >
              <GlassCard>
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles size={16} style={{ color: '#a5b4fc' }} />
                  <h3 className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                    Сгенерировать программу
                  </h3>
                </div>

                {/* Цель */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    🎯 Цель
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(GOAL_LABELS).map(([key, { label, icon }]) => (
                      <button
                        key={key}
                        onClick={() => setGenForm((f) => ({ ...f, goal_type: key }))}
                        className="px-2.5 py-1.5 rounded-lg text-xs font-medium"
                        style={{
                          background: genForm.goal_type === key ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: genForm.goal_type === key ? '#a5b4fc' : 'var(--app-hint)',
                          border: genForm.goal_type === key ? '1px solid rgba(99,102,241,0.4)' : '1px solid transparent',
                        }}
                      >
                        {icon} {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Уровень */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    📊 Уровень
                  </label>
                  <div className="flex gap-2">
                    {Object.entries(DIFF_LABELS).map(([key, label]) => (
                      <button
                        key={key}
                        onClick={() => setGenForm((f) => ({ ...f, difficulty: key }))}
                        className="flex-1 py-2 rounded-xl text-xs font-medium"
                        style={{
                          background: genForm.difficulty === key ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: genForm.difficulty === key ? '#a5b4fc' : 'var(--app-hint)',
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Место */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    📍 Место
                  </label>
                  <div className="flex gap-2">
                    {Object.entries(LOC_LABELS).map(([key, label]) => (
                      <button
                        key={key}
                        onClick={() => setGenForm((f) => ({ ...f, location: key }))}
                        className="flex-1 py-2 rounded-xl text-xs font-medium"
                        style={{
                          background: genForm.location === key ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: genForm.location === key ? '#a5b4fc' : 'var(--app-hint)',
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Дни в неделю и длительность */}
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      📅 Дней/нед
                    </label>
                    <div className="flex gap-1">
                      {[2, 3, 4, 5, 6].map((n) => (
                        <button
                          key={n}
                          onClick={() => setGenForm((f) => ({ ...f, days_per_week: n }))}
                          className="flex-1 py-2 rounded-lg text-xs font-medium"
                          style={{
                            background: genForm.days_per_week === n ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                            color: genForm.days_per_week === n ? '#a5b4fc' : 'var(--app-hint)',
                          }}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      ⏱️ Недель
                    </label>
                    <div className="flex gap-1">
                      {[4, 6, 8, 12].map((n) => (
                        <button
                          key={n}
                          onClick={() => setGenForm((f) => ({ ...f, duration_weeks: n }))}
                          className="flex-1 py-2 rounded-lg text-xs font-medium"
                          style={{
                            background: genForm.duration_weeks === n ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                            color: genForm.duration_weeks === n ? '#a5b4fc' : 'var(--app-hint)',
                          }}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Примечания */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                    📝 Примечания (необязательно)
                  </label>
                  <input
                    type="text"
                    value={genForm.notes || ''}
                    onChange={(e) => setGenForm((f) => ({ ...f, notes: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                    style={{ color: 'var(--app-text)' }}
                    placeholder="Акцент на верх тела, травма колена..."
                  />
                </div>

                {/* Кнопка генерации */}
                <button
                  onClick={handleGenerate}
                  disabled={generateMut.isPending}
                  className="w-full py-3 rounded-xl text-sm font-bold text-white flex items-center justify-center gap-2"
                  style={{
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    opacity: generateMut.isPending ? 0.6 : 1,
                  }}
                >
                  {generateMut.isPending ? (
                    <>
                      <Loader2 size={16} className="animate-spin" /> Генерация...
                    </>
                  ) : (
                    <>
                      <Sparkles size={16} /> Сгенерировать
                    </>
                  )}
                </button>
              </GlassCard>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Список программ ── */}
        {programs && programs.length > 0 ? (
          <div className="space-y-3">
            <div className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
              Мои программы ({programs.length})
            </div>
            {programs.map((prog) => {
              const goalInfo = GOAL_LABELS[prog.goal_type || ''] || { label: prog.goal_type, icon: '📋' }
              const isExpanded = expandedId === prog.id

              return (
                <GlassCard key={prog.id} noPadding>
                  {/* Заголовок программы */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : prog.id)}
                    className="w-full flex items-center justify-between p-4"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xl">{goalInfo.icon}</span>
                      <div className="text-left">
                        <div className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                          {prog.name}
                        </div>
                        <div className="flex items-center gap-2 text-[10px] mt-0.5" style={{ color: 'var(--app-hint)' }}>
                          <span>{DIFF_LABELS[prog.difficulty] || prog.difficulty}</span>
                          <span>·</span>
                          <span>{LOC_LABELS[prog.location] || prog.location}</span>
                          <span>·</span>
                          <span>{prog.days_per_week} дн/нед</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {prog.is_active && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                          style={{ background: 'rgba(34,197,94,0.2)', color: '#22c55e' }}>
                          Активна
                        </span>
                      )}
                      {isExpanded ? (
                        <ChevronUp size={16} style={{ color: 'var(--app-hint)' }} />
                      ) : (
                        <ChevronDown size={16} style={{ color: 'var(--app-hint)' }} />
                      )}
                    </div>
                  </button>

                  {/* Детали (если развёрнуто) */}
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-3">
                      {prog.description && (
                        <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
                          {prog.description}
                        </p>
                      )}

                      {/* Дни программы */}
                      <div className="space-y-1.5">
                        {prog.days.map((day) => (
                          <div
                            key={day.id}
                            className="flex items-start gap-2 p-2.5 rounded-xl"
                            style={{ background: 'rgba(255,255,255,0.03)' }}
                          >
                            <div
                              className="w-6 h-6 rounded-lg flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5"
                              style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}
                            >
                              {day.day_number}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--app-text)' }}>
                                {day.weekday != null && (
                                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0"
                                    style={{ background: 'rgba(251,146,60,0.15)', color: '#fb923c' }}>
                                    {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'][day.weekday]}
                                  </span>
                                )}
                                <span className="whitespace-pre-wrap">{day.day_name}</span>
                              </div>
                              {day.template_id && (
                                <div className="text-[10px] mt-0.5" style={{ color: '#22c55e' }}>● шаблон привязан</div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Кнопки действий */}
                      <div className="flex gap-2">
                        {/* Редактировать — всегда */}
                        <button
                          onClick={() => navigate(`/fitness/program/${prog.id}`)}
                          className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium"
                          style={{ background: 'rgba(99,102,241,0.15)', color: '#a5b4fc' }}
                        >
                          <Edit3 size={14} /> Редактировать
                        </button>

                        {/* Запустить — если не активна */}
                        {!prog.is_active && (
                          <button
                            onClick={() => activateMut.mutate(prog.id)}
                            disabled={activateMut.isPending}
                            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-medium"
                            style={{ background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}
                          >
                            <Play size={14} /> {activateMut.isPending ? 'Запуск...' : 'Запустить'}
                          </button>
                        )}

                        {/* Начать тренировку — если активна */}
                        {prog.is_active && (
                          <button
                            onClick={() => navigate('/fitness/workout', { state: { fromProgram: true } })}
                            className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold text-white"
                            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
                          >
                            <Dumbbell size={14} /> Тренировка
                          </button>
                        )}

                        {/* Удалить */}
                        <button
                          onClick={() => {
                          const doDelete = () => deleteMut.mutate(prog.id)
                          const tg = window.Telegram?.WebApp
                          if (tg?.showConfirm) {
                            tg.showConfirm('Удалить программу? Это действие нельзя отменить.', (ok: boolean) => { if (ok) doDelete() })
                          } else if (window.confirm('Удалить программу? Это действие нельзя отменить.')) {
                            doDelete()
                          }
                        }}
                          disabled={deleteMut.isPending}
                          className="px-3 py-2 rounded-xl"
                          style={{ background: 'rgba(239,68,68,0.1)' }}
                        >
                          <Trash2 size={14} style={{ color: '#ef4444' }} />
                        </button>
                      </div>
                    </div>
                  )}
                </GlassCard>
              )
            })}
          </div>
        ) : !showGenerate ? (
          /* Пустое состояние программ */
          <div className="flex flex-col items-center justify-center py-8">
            <div
              className="w-20 h-20 rounded-full flex items-center justify-center mb-4 text-3xl"
              style={{ background: 'rgba(99,102,241,0.1)' }}
            >
              📋
            </div>
            <p className="text-base font-bold mb-1" style={{ color: 'var(--app-text)' }}>
              Нет программ
            </p>
            <p className="text-sm text-center px-8 mb-4" style={{ color: 'var(--app-hint)' }}>
              Создай программу тренировок с помощью AI или вручную
            </p>
            <button
              onClick={() => setShowGenerate(true)}
              className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
            >
              <Sparkles size={16} /> Сгенерировать
            </button>
          </div>
        ) : null}

        {/* ══════════════════════════════════════════════════════════════════════
            Секция «Готовые шаблоны»
           ══════════════════════════════════════════════════════════════════════ */}
        {templates && templates.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <FileText size={14} style={{ color: '#fb923c' }} />
              <span className="text-xs font-medium" style={{ color: 'var(--app-hint)' }}>
                Шаблоны ({templates.length})
              </span>
            </div>
            {templates.map((tpl) => {
              const isExpanded = expandedTemplateId === tpl.id
              return (
                <GlassCard key={tpl.id} noPadding>
                  {/* Заголовок шаблона */}
                  <button
                    onClick={() => setExpandedTemplateId(isExpanded ? null : tpl.id)}
                    className="w-full flex items-center justify-between p-3"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center"
                        style={{ background: 'linear-gradient(135deg, rgba(251,146,60,0.2), rgba(234,88,12,0.1))' }}
                      >
                        <FileText size={18} style={{ color: '#fb923c' }} />
                      </div>
                      <div className="text-left">
                        <div className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                          {tpl.name}
                        </div>
                        <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                          {tpl.exercises?.length || 0} упражнений
                          {tpl.description ? ` · ${tpl.description}` : ''}
                        </div>
                      </div>
                    </div>
                    {isExpanded
                      ? <ChevronUp size={16} style={{ color: 'var(--app-hint)' }} />
                      : <ChevronDown size={16} style={{ color: 'var(--app-hint)' }} />}
                  </button>

                  {/* Детали шаблона — список упражнений */}
                  {isExpanded && (
                    <div className="px-3 pb-3 space-y-2">
                      {/* Упражнения */}
                      {tpl.exercises && tpl.exercises.length > 0 && (
                        <div className="space-y-1">
                          {tpl.exercises.map((ex, idx) => (
                            <div key={ex.id || idx}
                              className="flex items-center gap-2 px-2.5 py-2 rounded-lg"
                              style={{ background: 'rgba(255,255,255,0.03)' }}>
                              <Dumbbell size={12} style={{ color: '#818cf8' }} />
                              <span className="text-xs flex-1" style={{ color: 'var(--app-text)' }}>
                                {ex.exercise_name || `Упражнение #${ex.exercise_id}`}
                              </span>
                              <span className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                                {ex.sets}×{ex.reps || '—'}
                                {ex.weight_kg ? ` · ${ex.weight_kg} кг` : ''}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Кнопки действий */}
                      <div className="flex gap-2 pt-1">
                        <button
                          onClick={() => handleApplyTemplate(tpl.id)}
                          disabled={applyTemplateMut.isPending}
                          className="flex-1 flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-xs font-bold text-white"
                          style={{
                            background: 'linear-gradient(135deg, #22c55e, #16a34a)',
                            opacity: applyTemplateMut.isPending ? 0.6 : 1,
                          }}
                        >
                          <Play size={14} />
                          {applyTemplateMut.isPending ? 'Создание...' : 'Начать тренировку'}
                        </button>
                        <button
                          onClick={() => deleteTemplateMut.mutate(tpl.id)}
                          disabled={deleteTemplateMut.isPending}
                          className="px-3 py-2 rounded-xl"
                          style={{ background: 'rgba(239,68,68,0.1)' }}
                        >
                          <Trash2 size={14} style={{ color: '#ef4444' }} />
                        </button>
                      </div>
                    </div>
                  )}
                </GlassCard>
              )
            })}
          </div>
        )}
      </div>
      {toastMsg && <Toast message={toastMsg} onClose={() => setToastMsg('')} />}
    </div>
  )
}
