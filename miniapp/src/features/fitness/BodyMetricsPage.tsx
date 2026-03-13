/**
 * Страница замеров тела.
 * Блок «Моя цель», форма ввода замеров, график веса (AreaChart),
 * график замеров (мульти-линия), история замеров.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Plus, X, Target, Edit3, Camera, Trash2 } from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts'
import {
  useBodyMetrics, useCreateBodyMetric, useFitnessGoals, useUpdateFitnessGoals,
  useProgressPhotos, useUploadPhoto, useDeletePhoto,
  type BodyMetricCreateDto, type FitnessGoal,
} from '../../api/fitness'
import { GlassCard } from '../../shared/ui/GlassCard'

/** Метки целей */
const GOAL_TYPE_LABELS: Record<string, { label: string; icon: string }> = {
  gain_muscle: { label: 'Набор массы', icon: '💪' },
  lose_weight: { label: 'Похудение', icon: '🔥' },
  maintain: { label: 'Поддержание', icon: '⚖️' },
  endurance: { label: 'Выносливость', icon: '🏃' },
  strength: { label: 'Сила', icon: '🏋️' },
  home_fitness: { label: 'Домашний фитнес', icon: '🏠' },
  return_to_form: { label: 'Возвращение', icon: '🔄' },
}

/** Метки уровней */
const LEVEL_LABELS: Record<string, string> = {
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

/** Кастомный тултип */
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
          {p.name}: {typeof p.value === 'number' ? Math.round(p.value * 10) / 10 : p.value}
        </div>
      ))}
    </div>
  )
}

export function BodyMetricsPage() {
  const navigate = useNavigate()
  const { data: metrics } = useBodyMetrics(180) // 6 месяцев
  const createMetric = useCreateBodyMetric()

  // Цели
  const { data: goals } = useFitnessGoals()
  const updateGoals = useUpdateFitnessGoals()

  // Формы
  const [showForm, setShowForm] = useState(false)
  const [showGoalForm, setShowGoalForm] = useState(false)
  const [form, setForm] = useState<BodyMetricCreateDto>({})
  // Форма целей — инициализируем из текущих данных
  const [goalForm, setGoalForm] = useState<Partial<FitnessGoal>>({})

  // Фото прогресса
  const { data: photos } = useProgressPhotos()
  const uploadPhoto = useUploadPhoto()
  const deletePhoto = useDeletePhoto()
  const [showCompare, setShowCompare] = useState(false)

  // Загрузка фото через file input
  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      await uploadPhoto.mutateAsync({ file })
    } catch (err) {
      console.error('Ошибка загрузки фото:', err)
    }
    // Сбрасываем input для повторной загрузки того же файла
    e.target.value = ''
  }

  // Удалить фото
  const handleDeletePhoto = async (id: number) => {
    try {
      await deletePhoto.mutateAsync(id)
    } catch (err) {
      console.error('Ошибка удаления фото:', err)
    }
  }

  // Обновить поле формы замера
  const setField = (key: string, value: string) => {
    const num = parseFloat(value)
    setForm((prev) => ({ ...prev, [key]: value === '' ? null : (isNaN(num) ? null : num) }))
  }

  // Сохранить замер
  const handleSave = async () => {
    const hasData = Object.values(form).some((v) => v !== null && v !== undefined)
    if (!hasData) return
    try {
      await createMetric.mutateAsync(form)
      setForm({})
      setShowForm(false)
    } catch (e) {
      console.error('Ошибка сохранения замера:', e)
    }
  }

  // Открыть форму редактирования целей
  const openGoalForm = () => {
    // Инициализируем форму текущими значениями цели
    setGoalForm({
      goal_type: goals?.goal_type || 'maintain',
      workouts_per_week: goals?.workouts_per_week || 3,
      preferred_duration_min: goals?.preferred_duration_min || 60,
      training_location: goals?.training_location || 'gym',
      experience_level: goals?.experience_level || 'intermediate',
      target_weight_kg: goals?.target_weight_kg ?? undefined,
    })
    setShowGoalForm(true)
  }

  // Сохранить цель
  const handleSaveGoal = async () => {
    try {
      await updateGoals.mutateAsync(goalForm)
      setShowGoalForm(false)
    } catch (e) {
      console.error('Ошибка сохранения цели:', e)
    }
  }

  // Подготовка данных для графиков
  const allMetrics = (metrics || []).slice().reverse() // хронологический порядок

  // График веса
  const weightData = allMetrics
    .filter((m) => m.weight_kg)
    .map((m) => ({
      date: m.logged_at
        ? new Date(m.logged_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
        : '',
      weight: m.weight_kg,
    }))

  // График замеров (грудь, талия, бёдра)
  const measureData = allMetrics
    .filter((m) => m.chest_cm || m.waist_cm || m.hips_cm)
    .map((m) => ({
      date: m.logged_at
        ? new Date(m.logged_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
        : '',
      chest: m.chest_cm,
      waist: m.waist_cm,
      hips: m.hips_cm,
    }))

  // Последний замер
  const latest = metrics?.[0]

  // Информация о цели для отображения
  const goalInfo = GOAL_TYPE_LABELS[goals?.goal_type || ''] || { label: goals?.goal_type || 'Не задана', icon: '🎯' }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/fitness')} className="p-2 -ml-2">
            <ArrowLeft size={22} style={{ color: 'var(--app-text)' }} />
          </button>
          <h1 className="text-xl font-bold" style={{ color: 'var(--app-text)' }}>
            Замеры тела
          </h1>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="p-2 rounded-xl"
          style={{ background: 'rgba(99,102,241,0.2)' }}
        >
          {showForm ? <X size={20} style={{ color: '#818cf8' }} /> : <Plus size={20} style={{ color: '#818cf8' }} />}
        </button>
      </div>

      {/* Контент */}
      <div className="flex-1 overflow-y-auto px-4 pb-24 space-y-4">

        {/* ══ Блок «Моя цель» ══ */}
        <GlassCard>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Target size={16} style={{ color: '#a5b4fc' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                Моя цель
              </span>
            </div>
            <button onClick={openGoalForm} className="p-1">
              <Edit3 size={14} style={{ color: 'var(--app-hint)' }} />
            </button>
          </div>
          {goals ? (
            <div className="grid grid-cols-2 gap-3">
              {/* Тип цели */}
              <div className="flex items-center gap-2 p-2.5 rounded-xl"
                style={{ background: 'rgba(99,102,241,0.08)' }}>
                <span className="text-lg">{goalInfo.icon}</span>
                <div>
                  <div className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>
                    {goalInfo.label}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>цель</div>
                </div>
              </div>
              {/* Тренировок в неделю */}
              <div className="flex items-center gap-2 p-2.5 rounded-xl"
                style={{ background: 'rgba(34,197,94,0.08)' }}>
                <span className="text-lg">📅</span>
                <div>
                  <div className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>
                    {goals.workouts_per_week}× в неделю
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>тренировок</div>
                </div>
              </div>
              {/* Длительность */}
              <div className="flex items-center gap-2 p-2.5 rounded-xl"
                style={{ background: 'rgba(251,146,60,0.08)' }}>
                <span className="text-lg">⏱️</span>
                <div>
                  <div className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>
                    {goals.preferred_duration_min} мин
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>тренировка</div>
                </div>
              </div>
              {/* Уровень + место */}
              <div className="flex items-center gap-2 p-2.5 rounded-xl"
                style={{ background: 'rgba(236,72,153,0.08)' }}>
                <span className="text-lg">📍</span>
                <div>
                  <div className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>
                    {LOC_LABELS[goals.training_location] || goals.training_location}
                  </div>
                  <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    {LEVEL_LABELS[goals.experience_level] || goals.experience_level}
                  </div>
                </div>
              </div>
              {/* Целевой вес — показываем если задан */}
              {goals.target_weight_kg && (
                <div className="flex items-center gap-2 p-2.5 rounded-xl col-span-2"
                  style={{ background: 'rgba(34,197,94,0.08)' }}>
                  <span className="text-lg">🎯</span>
                  <div>
                    <div className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>
                      {goals.target_weight_kg} кг
                    </div>
                    <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>целевой вес</div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button onClick={openGoalForm}
              className="w-full py-3 rounded-xl text-sm font-medium border border-dashed border-white/[0.15]"
              style={{ color: '#a5b4fc' }}>
              Установить цель
            </button>
          )}
        </GlassCard>

        {/* ── Форма редактирования цели ── */}
        <AnimatePresence>
          {showGoalForm && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
            >
              <GlassCard>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold" style={{ color: 'var(--app-text)' }}>
                    Настроить цель
                  </h3>
                  <button onClick={() => setShowGoalForm(false)}>
                    <X size={18} style={{ color: 'var(--app-hint)' }} />
                  </button>
                </div>

                {/* Тип цели */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    🎯 Цель
                  </label>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(GOAL_TYPE_LABELS).map(([key, { label, icon }]) => (
                      <button key={key}
                        onClick={() => setGoalForm((f) => ({ ...f, goal_type: key }))}
                        className="px-2.5 py-1.5 rounded-lg text-xs font-medium"
                        style={{
                          background: goalForm.goal_type === key ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: goalForm.goal_type === key ? '#a5b4fc' : 'var(--app-hint)',
                          border: goalForm.goal_type === key ? '1px solid rgba(99,102,241,0.4)' : '1px solid transparent',
                        }}>
                        {icon} {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Тренировок в неделю */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    📅 Тренировок в неделю
                  </label>
                  <div className="flex gap-1.5">
                    {[2, 3, 4, 5, 6, 7].map((n) => (
                      <button key={n}
                        onClick={() => setGoalForm((f) => ({ ...f, workouts_per_week: n }))}
                        className="flex-1 py-2 rounded-lg text-xs font-medium"
                        style={{
                          background: goalForm.workouts_per_week === n ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: goalForm.workouts_per_week === n ? '#a5b4fc' : 'var(--app-hint)',
                        }}>
                        {n}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Длительность */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    ⏱️ Длительность тренировки (мин)
                  </label>
                  <div className="flex gap-1.5">
                    {[30, 45, 60, 90, 120].map((n) => (
                      <button key={n}
                        onClick={() => setGoalForm((f) => ({ ...f, preferred_duration_min: n }))}
                        className="flex-1 py-2 rounded-lg text-xs font-medium"
                        style={{
                          background: goalForm.preferred_duration_min === n ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: goalForm.preferred_duration_min === n ? '#a5b4fc' : 'var(--app-hint)',
                        }}>
                        {n}
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
                    {Object.entries(LEVEL_LABELS).map(([key, label]) => (
                      <button key={key}
                        onClick={() => setGoalForm((f) => ({ ...f, experience_level: key }))}
                        className="flex-1 py-2 rounded-xl text-xs font-medium"
                        style={{
                          background: goalForm.experience_level === key ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: goalForm.experience_level === key ? '#a5b4fc' : 'var(--app-hint)',
                        }}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Место */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    📍 Место тренировок
                  </label>
                  <div className="flex gap-2">
                    {Object.entries(LOC_LABELS).map(([key, label]) => (
                      <button key={key}
                        onClick={() => setGoalForm((f) => ({ ...f, training_location: key }))}
                        className="flex-1 py-2 rounded-xl text-xs font-medium"
                        style={{
                          background: goalForm.training_location === key ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)',
                          color: goalForm.training_location === key ? '#a5b4fc' : 'var(--app-hint)',
                        }}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Целевой вес */}
                <div className="mb-3">
                  <label className="text-[10px] block mb-1.5" style={{ color: 'var(--app-hint)' }}>
                    ⚖️ Целевой вес (кг)
                  </label>
                  <input type="number" value={goalForm.target_weight_kg ?? ''}
                    onChange={(e) => {
                      // Парсим значение, пустую строку трактуем как сброс
                      const val = e.target.value === '' ? undefined : parseFloat(e.target.value)
                      setGoalForm((f) => ({ ...f, target_weight_kg: val }))
                    }}
                    className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                    style={{ color: 'var(--app-text)' }} placeholder="75.0" inputMode="decimal" />
                </div>

                {/* Сохранить */}
                <button onClick={handleSaveGoal}
                  disabled={updateGoals.isPending}
                  className="w-full py-2.5 rounded-xl text-sm font-bold text-white"
                  style={{
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    opacity: updateGoals.isPending ? 0.6 : 1,
                  }}>
                  {updateGoals.isPending ? 'Сохранение...' : 'Сохранить цель'}
                </button>
              </GlassCard>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Форма ввода замеров ── */}
        <AnimatePresence>
          {showForm && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
            >
              <GlassCard>
                <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--app-text)' }}>
                  Новый замер
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  {/* Вес */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      ⚖️ Вес (кг)
                    </label>
                    <input type="number" value={form.weight_kg ?? ''}
                      onChange={(e) => setField('weight_kg', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="75.0" inputMode="decimal" />
                  </div>
                  {/* % жира */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      📊 % жира
                    </label>
                    <input type="number" value={form.body_fat_pct ?? ''}
                      onChange={(e) => setField('body_fat_pct', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="15" inputMode="decimal" />
                  </div>
                  {/* Грудь */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      📏 Грудь (см)
                    </label>
                    <input type="number" value={form.chest_cm ?? ''}
                      onChange={(e) => setField('chest_cm', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="100" inputMode="decimal" />
                  </div>
                  {/* Талия */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      📏 Талия (см)
                    </label>
                    <input type="number" value={form.waist_cm ?? ''}
                      onChange={(e) => setField('waist_cm', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="80" inputMode="decimal" />
                  </div>
                  {/* Бёдра */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      📏 Бёдра (см)
                    </label>
                    <input type="number" value={form.hips_cm ?? ''}
                      onChange={(e) => setField('hips_cm', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="95" inputMode="decimal" />
                  </div>
                  {/* Бицепс */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      💪 Бицепс (см)
                    </label>
                    <input type="number" value={form.bicep_cm ?? ''}
                      onChange={(e) => setField('bicep_cm', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="36" inputMode="decimal" />
                  </div>
                  {/* Энергия */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      ⚡ Энергия (1-5)
                    </label>
                    <input type="number" value={form.energy_level ?? ''}
                      onChange={(e) => setField('energy_level', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="4" inputMode="numeric" />
                  </div>
                  {/* Сон */}
                  <div>
                    <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                      🌙 Сон (часов)
                    </label>
                    <input type="number" value={form.sleep_hours ?? ''}
                      onChange={(e) => setField('sleep_hours', e.target.value)}
                      className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                      style={{ color: 'var(--app-text)' }} placeholder="7.5" inputMode="decimal" />
                  </div>
                </div>
                {/* Заметки */}
                <div className="mt-3">
                  <label className="text-[10px] block mb-1" style={{ color: 'var(--app-hint)' }}>
                    📝 Заметки
                  </label>
                  <input type="text" value={form.notes ?? ''}
                    onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
                    className="w-full px-3 py-2 rounded-xl text-sm bg-transparent border border-white/[0.08] outline-none"
                    style={{ color: 'var(--app-text)' }} placeholder="Самочувствие, ощущения..." />
                </div>
                {/* Кнопка сохранить */}
                <button onClick={handleSave} disabled={createMetric.isPending}
                  className="w-full mt-3 py-2.5 rounded-xl text-sm font-bold text-white"
                  style={{
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                    opacity: createMetric.isPending ? 0.6 : 1,
                  }}>
                  {createMetric.isPending ? 'Сохранение...' : 'Сохранить замер'}
                </button>
              </GlassCard>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Последний замер ── */}
        {latest && (
          <GlassCard className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl"
              style={{ background: 'rgba(34,197,94,0.15)' }}>
              ⚖️
            </div>
            <div className="flex-1">
              <div className="text-2xl font-bold" style={{ color: 'var(--app-text)' }}>
                {latest.weight_kg ? `${latest.weight_kg} кг` : '—'}
              </div>
              <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                {latest.logged_at
                  ? new Date(latest.logged_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
                  : 'Последний замер'}
              </div>
            </div>
            {latest.body_fat_pct && (
              <div className="text-right">
                <div className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                  {latest.body_fat_pct}%
                </div>
                <div className="text-[10px]" style={{ color: 'var(--app-hint)' }}>жира</div>
              </div>
            )}
          </GlassCard>
        )}

        {/* ── График веса тела ── */}
        {weightData.length > 1 && (
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                ⚖️ Динамика веса
              </span>
              <span className="text-xs" style={{ color: 'var(--app-hint)' }}>
                {weightData.length} замеров
              </span>
            </div>
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={weightData}>
                  <defs>
                    <linearGradient id="bodyWeightGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="date" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis domain={['auto', 'auto']} tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} axisLine={false} tickLine={false} width={35} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="weight" stroke="#22c55e" strokeWidth={2} fill="url(#bodyWeightGrad)" dot={{ r: 3, fill: '#22c55e' }} name="Вес" />
                  {/* Пунктирная линия целевого веса */}
                  {goals?.target_weight_kg && (
                    <ReferenceLine
                      y={goals.target_weight_kg}
                      stroke="#a5b4fc"
                      strokeDasharray="6 3"
                      strokeWidth={1.5}
                      label={{
                        value: `Цель: ${goals.target_weight_kg} кг`,
                        position: 'right',
                        fill: '#a5b4fc',
                        fontSize: 10,
                      }}
                    />
                  )}
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        )}

        {/* ── График замеров (мульти-линия) ── */}
        {measureData.length > 1 && (
          <GlassCard>
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                📏 Замеры тела
              </span>
            </div>
            <div className="h-[180px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={measureData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="date" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }} axisLine={false} tickLine={false} width={35} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="chest" stroke="#6366f1" strokeWidth={2} dot={{ r: 2 }} name="Грудь" connectNulls />
                  <Line type="monotone" dataKey="waist" stroke="#f59e0b" strokeWidth={2} dot={{ r: 2 }} name="Талия" connectNulls />
                  <Line type="monotone" dataKey="hips" stroke="#ec4899" strokeWidth={2} dot={{ r: 2 }} name="Бёдра" connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {/* Легенда */}
            <div className="flex justify-center gap-4 mt-2 text-[10px]">
              <span style={{ color: '#6366f1' }}>● Грудь</span>
              <span style={{ color: '#f59e0b' }}>● Талия</span>
              <span style={{ color: '#ec4899' }}>● Бёдра</span>
            </div>
          </GlassCard>
        )}

        {/* ── Фото прогресса ── */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Camera size={16} style={{ color: '#a5b4fc' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>
                Фото прогресса
              </span>
              {photos && photos.length > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full"
                  style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}>
                  {photos.length}
                </span>
              )}
            </div>
            <label className="p-2 rounded-xl cursor-pointer"
              style={{ background: 'rgba(99,102,241,0.2)' }}>
              <Camera size={16} style={{ color: '#818cf8' }} />
              <input type="file" accept="image/*" capture="environment"
                onChange={handlePhotoUpload} className="hidden" />
            </label>
          </div>

          {/* Загрузка... */}
          {uploadPhoto.isPending && (
            <div className="text-xs text-center py-3" style={{ color: 'var(--app-hint)' }}>
              Загрузка фото...
            </div>
          )}

          {/* Сетка фото */}
          {photos && photos.length > 0 ? (
            <>
              <div className="grid grid-cols-3 gap-2">
                {photos.slice(0, 9).map((p) => (
                  <div key={p.id} className="relative aspect-[3/4] rounded-xl overflow-hidden group"
                    style={{ background: 'rgba(255,255,255,0.04)' }}>
                    <img src={p.url} alt="Прогресс"
                      className="w-full h-full object-cover" loading="lazy" />
                    {/* Дата поверх фото */}
                    <div className="absolute bottom-0 left-0 right-0 px-1.5 py-1 text-[9px] font-medium"
                      style={{ background: 'linear-gradient(transparent, rgba(0,0,0,0.7))', color: '#fff' }}>
                      {p.logged_at
                        ? new Date(p.logged_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                        : ''}
                    </div>
                    {/* Кнопка удаления */}
                    <button
                      onClick={() => handleDeletePhoto(p.id)}
                      className="absolute top-1 right-1 p-1 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                      style={{ background: 'rgba(0,0,0,0.6)' }}>
                      <Trash2 size={12} style={{ color: '#f87171' }} />
                    </button>
                  </div>
                ))}
              </div>

              {/* Кнопка до/после — показываем если >= 2 фото */}
              {photos.length >= 2 && (
                <button
                  onClick={() => setShowCompare(!showCompare)}
                  className="w-full mt-3 py-2 rounded-xl text-xs font-medium border border-white/[0.1]"
                  style={{ color: '#a5b4fc' }}>
                  {showCompare ? 'Скрыть сравнение' : '📸 До / После'}
                </button>
              )}

              {/* Сравнение до/после */}
              <AnimatePresence>
                {showCompare && photos.length >= 2 && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-3"
                  >
                    <div className="flex gap-2">
                      {/* Первое фото (самое старое) */}
                      <div className="flex-1">
                        <div className="text-[10px] text-center mb-1" style={{ color: 'var(--app-hint)' }}>
                          До
                        </div>
                        <div className="aspect-[3/4] rounded-xl overflow-hidden"
                          style={{ background: 'rgba(255,255,255,0.04)' }}>
                          <img src={photos[photos.length - 1].url} alt="До"
                            className="w-full h-full object-cover" />
                        </div>
                        <div className="text-[9px] text-center mt-1" style={{ color: 'var(--app-hint)' }}>
                          {photos[photos.length - 1].logged_at
                            ? new Date(photos[photos.length - 1].logged_at!).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                            : ''}
                        </div>
                      </div>
                      {/* Последнее фото (самое новое) */}
                      <div className="flex-1">
                        <div className="text-[10px] text-center mb-1" style={{ color: 'var(--app-hint)' }}>
                          После
                        </div>
                        <div className="aspect-[3/4] rounded-xl overflow-hidden"
                          style={{ background: 'rgba(255,255,255,0.04)' }}>
                          <img src={photos[0].url} alt="После"
                            className="w-full h-full object-cover" />
                        </div>
                        <div className="text-[9px] text-center mt-1" style={{ color: 'var(--app-hint)' }}>
                          {photos[0].logged_at
                            ? new Date(photos[0].logged_at!).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
                            : ''}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          ) : (
            <div className="text-center py-4">
              <div className="text-2xl mb-2">📷</div>
              <p className="text-xs" style={{ color: 'var(--app-hint)' }}>
                Делай фото для отслеживания визуального прогресса
              </p>
              <label className="inline-block mt-2 px-4 py-2 rounded-xl text-xs font-medium cursor-pointer"
                style={{ background: 'rgba(99,102,241,0.2)', color: '#a5b4fc' }}>
                Загрузить фото
                <input type="file" accept="image/*" capture="environment"
                  onChange={handlePhotoUpload} className="hidden" />
              </label>
            </div>
          )}
        </GlassCard>

        {/* ── История замеров ── */}
        {metrics && metrics.length > 0 && (
          <div>
            <div className="text-xs font-medium mb-2" style={{ color: 'var(--app-hint)' }}>
              История
            </div>
            <div className="space-y-2">
              {metrics.slice(0, 20).map((m) => (
                <GlassCard key={m.id} className="!p-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs" style={{ color: 'var(--app-hint)' }}>
                      {m.logged_at
                        ? new Date(m.logged_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
                        : ''}
                    </div>
                    <div className="flex gap-3 text-xs">
                      {m.weight_kg && <span style={{ color: 'var(--app-text)' }}>⚖️ {m.weight_kg} кг</span>}
                      {m.body_fat_pct && <span style={{ color: 'var(--app-text)' }}>📊 {m.body_fat_pct}%</span>}
                    </div>
                  </div>
                  <div className="flex gap-3 mt-1 text-[10px]" style={{ color: 'var(--app-hint)' }}>
                    {m.chest_cm && <span>Грудь: {m.chest_cm}</span>}
                    {m.waist_cm && <span>Талия: {m.waist_cm}</span>}
                    {m.hips_cm && <span>Бёдра: {m.hips_cm}</span>}
                    {m.bicep_cm && <span>Бицепс: {m.bicep_cm}</span>}
                    {m.energy_level && <span>⚡{m.energy_level}</span>}
                    {m.sleep_hours && <span>🌙{m.sleep_hours}ч</span>}
                  </div>
                  {m.notes && (
                    <div className="mt-1 text-[10px]" style={{ color: 'var(--app-hint)' }}>{m.notes}</div>
                  )}
                </GlassCard>
              ))}
            </div>
          </div>
        )}

        {/* Пустое состояние */}
        {(!metrics || metrics.length === 0) && !showForm && (
          <div className="flex flex-col items-center justify-center py-8">
            <div className="w-20 h-20 rounded-full flex items-center justify-center mb-4 text-3xl"
              style={{ background: 'rgba(34,197,94,0.1)' }}>
              ⚖️
            </div>
            <p className="text-base font-bold mb-1" style={{ color: 'var(--app-text)' }}>Нет замеров</p>
            <p className="text-sm text-center px-8 mb-4" style={{ color: 'var(--app-hint)' }}>
              Записывай вес и замеры тела для отслеживания прогресса
            </p>
            <button onClick={() => setShowForm(true)}
              className="px-6 py-2.5 rounded-xl text-sm font-bold text-white"
              style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}>
              Добавить замер
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
