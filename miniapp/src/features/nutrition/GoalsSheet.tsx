/**
 * Визард настройки целей по питанию (3 шага).
 * Шаг 1: Выбор цели (похудение / удержание / набор)
 * Шаг 2: Параметры тела (вес, рост, возраст, пол, активность)
 * Шаг 3: Рассчитанные КБЖУ с возможностью ручной коррекции
 */
import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, ChevronLeft, Flame, Scale, Dumbbell, Calculator } from 'lucide-react'
import {
  useGoals,
  useUpdateGoals,
  useProfile,
  useUpdateProfile,
  useCalculateGoals,
} from '../../api/nutrition'

interface GoalsSheetProps {
  open: boolean
  onClose: () => void
}

// ── Константы для карточек выбора ────────────────────────────────────────────

const GOAL_OPTIONS = [
  { value: 'lose', label: 'Похудение', icon: Flame, emoji: '🔥', desc: 'Дефицит 500 ккал, высокий белок' },
  { value: 'maintain', label: 'Удержание', icon: Scale, emoji: '⚖️', desc: 'Поддержание текущего веса' },
  { value: 'gain', label: 'Набор массы', icon: Dumbbell, emoji: '💪', desc: 'Профицит 300 ккал, высокий белок' },
] as const

const ACTIVITY_OPTIONS = [
  { value: 'sedentary', label: 'Сидячий', desc: 'Офис, мало движения' },
  { value: 'light', label: 'Лёгкий', desc: '1–3 тренировки/нед' },
  { value: 'moderate', label: 'Умеренный', desc: '3–5 тренировок/нед' },
  { value: 'active', label: 'Активный', desc: '6–7 тренировок/нед' },
  { value: 'very_active', label: 'Очень активный', desc: '2 тренировки/день' },
] as const

const GENDER_OPTIONS = [
  { value: 'male', label: 'Мужской' },
  { value: 'female', label: 'Женский' },
] as const

export function GoalsSheet({ open, onClose }: GoalsSheetProps) {
  // API хуки
  const { data: goals } = useGoals()
  const { data: profile } = useProfile()
  const updateGoals = useUpdateGoals()
  const updateProfile = useUpdateProfile()
  const calcGoals = useCalculateGoals()

  // Текущий шаг визарда (1, 2, 3)
  const [step, setStep] = useState(1)

  // Шаг 1 — тип цели
  const [goalType, setGoalType] = useState<string>('maintain')

  // Шаг 2 — параметры тела
  const [weight, setWeight] = useState(70)
  const [height, setHeight] = useState(170)
  const [age, setAge] = useState(30)
  const [gender, setGender] = useState<string>('male')
  const [activity, setActivity] = useState<string>('moderate')

  // Шаг 3 — рассчитанные цели (с возможностью ручной правки)
  const [calories, setCalories] = useState(2000)
  const [protein, setProtein] = useState(120)
  const [fat, setFat] = useState(65)
  const [carbs, setCarbs] = useState(250)
  const [water, setWater] = useState(2000)

  // Предзаполнение из сохранённых данных
  useEffect(() => {
    if (goals) {
      if (goals.goal_type) setGoalType(goals.goal_type)
      if (goals.activity_level) setActivity(goals.activity_level)
      setCalories(goals.calories ?? 2000)
      setProtein(goals.protein_g ?? 120)
      setFat(goals.fat_g ?? 65)
      setCarbs(goals.carbs_g ?? 250)
      setWater(goals.water_ml ?? 2000)
    }
  }, [goals])

  useEffect(() => {
    if (profile) {
      if (profile.weight_kg) setWeight(profile.weight_kg)
      if (profile.height_cm) setHeight(profile.height_cm)
      if (profile.age) setAge(profile.age)
      if (profile.gender) setGender(profile.gender)
    }
  }, [profile])

  // Сброс шага при открытии
  useEffect(() => {
    if (open) setStep(1)
  }, [open])

  // Переход на шаг 3 — расчёт целей
  const handleCalculate = () => {
    calcGoals.mutate(
      { goal_type: goalType, activity_level: activity, weight_kg: weight, height_cm: height, age, gender, water_ml: water },
      {
        onSuccess: (data) => {
          // Заполняем рассчитанные значения
          setCalories(data.calories)
          setProtein(data.protein_g)
          setFat(data.fat_g)
          setCarbs(data.carbs_g)
          setWater(data.water_ml)
          setStep(3)
        },
      }
    )
  }

  // Сохранение всего — профиль + цели
  const handleSave = async () => {
    // Сохраняем профиль
    await updateProfile.mutateAsync({ weight_kg: weight, height_cm: height, age, gender })
    // Сохраняем цели
    await updateGoals.mutateAsync({
      calories, protein_g: protein, fat_g: fat, carbs_g: carbs, water_ml: water,
      goal_type: goalType, activity_level: activity,
    })
    onClose()
  }

  const isSaving = updateGoals.isPending || updateProfile.isPending

  // ── Рендер шагов ───────────────────────────────────────────────────────────

  const renderStep1 = () => (
    <div className="flex flex-col gap-3">
      <p className="text-xs mb-1" style={{ color: 'var(--app-hint)' }}>Выберите вашу цель</p>
      {GOAL_OPTIONS.map((opt) => {
        const selected = goalType === opt.value
        return (
          <motion.button
            key={opt.value}
            onClick={() => setGoalType(opt.value)}
            className="flex items-center gap-3 p-3 rounded-xl text-left border transition-colors"
            style={{
              borderColor: selected ? '#8b5cf6' : 'rgba(255,255,255,0.08)',
              background: selected ? 'rgba(139,92,246,0.12)' : 'transparent',
            }}
            whileTap={{ scale: 0.98 }}
          >
            <span className="text-2xl">{opt.emoji}</span>
            <div className="flex-1">
              <div className="text-sm font-medium" style={{ color: 'var(--app-text)' }}>{opt.label}</div>
              <div className="text-[11px]" style={{ color: 'var(--app-hint)' }}>{opt.desc}</div>
            </div>
            {/* Индикатор выбора */}
            <div
              className="w-5 h-5 rounded-full border-2 flex items-center justify-center"
              style={{ borderColor: selected ? '#8b5cf6' : 'rgba(255,255,255,0.15)' }}
            >
              {selected && <div className="w-2.5 h-2.5 rounded-full" style={{ background: '#8b5cf6' }} />}
            </div>
          </motion.button>
        )
      })}

      <motion.button
        onClick={() => setStep(2)}
        className="w-full mt-2 py-3 rounded-xl text-sm font-medium text-white"
        style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
        whileTap={{ scale: 0.97 }}
      >
        Далее →
      </motion.button>
    </div>
  )

  const renderStep2 = () => (
    <div className="flex flex-col gap-3">
      <p className="text-xs mb-1" style={{ color: 'var(--app-hint)' }}>Параметры тела для расчёта КБЖУ</p>

      {/* Пол */}
      <div>
        <label className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>Пол</label>
        <div className="flex gap-2 mt-1">
          {GENDER_OPTIONS.map((g) => (
            <button
              key={g.value}
              onClick={() => setGender(g.value)}
              className="flex-1 py-2 rounded-xl text-xs font-medium border transition-colors"
              style={{
                borderColor: gender === g.value ? '#8b5cf6' : 'rgba(255,255,255,0.08)',
                background: gender === g.value ? 'rgba(139,92,246,0.12)' : 'transparent',
                color: 'var(--app-text)',
              }}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      {/* Числовые поля: вес, рост, возраст */}
      {[
        { label: 'Вес (кг)', value: weight, set: setWeight, min: 30, max: 250 },
        { label: 'Рост (см)', value: height, set: setHeight, min: 100, max: 250 },
        { label: 'Возраст', value: age, set: setAge, min: 10, max: 120 },
      ].map((f) => (
        <div key={f.label}>
          <label className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>{f.label}</label>
          <input
            type="number"
            inputMode="numeric"
            value={f.value || ''}
            onChange={(e) => f.set(Number(e.target.value) || 0)}
            onBlur={() => {
              if (f.value < f.min) f.set(f.min)
              if (f.value > f.max) f.set(f.max)
            }}
            className="w-full mt-1 px-3 py-2 rounded-xl text-sm bg-transparent outline-none border border-white/[0.08]"
            style={{ color: 'var(--app-text)' }}
          />
        </div>
      ))}

      {/* Уровень активности */}
      <div>
        <label className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>Активность</label>
        <div className="flex flex-col gap-1.5 mt-1">
          {ACTIVITY_OPTIONS.map((a) => {
            const sel = activity === a.value
            return (
              <button
                key={a.value}
                onClick={() => setActivity(a.value)}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-left border transition-colors"
                style={{
                  borderColor: sel ? '#8b5cf6' : 'rgba(255,255,255,0.08)',
                  background: sel ? 'rgba(139,92,246,0.12)' : 'transparent',
                }}
              >
                <div className="flex-1">
                  <span className="text-xs font-medium" style={{ color: 'var(--app-text)' }}>{a.label}</span>
                  <span className="text-[10px] ml-1.5" style={{ color: 'var(--app-hint)' }}>{a.desc}</span>
                </div>
                <div
                  className="w-4 h-4 rounded-full border-2 flex items-center justify-center"
                  style={{ borderColor: sel ? '#8b5cf6' : 'rgba(255,255,255,0.15)' }}
                >
                  {sel && <div className="w-2 h-2 rounded-full" style={{ background: '#8b5cf6' }} />}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      <motion.button
        onClick={handleCalculate}
        disabled={calcGoals.isPending}
        className="w-full mt-2 py-3 rounded-xl text-sm font-medium text-white flex items-center justify-center gap-2"
        style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
        whileTap={{ scale: 0.97 }}
      >
        <Calculator size={16} />
        {calcGoals.isPending ? 'Считаю...' : 'Рассчитать КБЖУ →'}
      </motion.button>
    </div>
  )

  const renderStep3 = () => (
    <div className="flex flex-col gap-3">
      <p className="text-xs mb-1" style={{ color: 'var(--app-hint)' }}>
        Рассчитанные цели — можно скорректировать вручную
      </p>

      {[
        { label: 'Калории (ккал)', value: calories, set: setCalories, color: '#f59e0b' },
        { label: 'Белки (г)', value: protein, set: setProtein, color: '#ef4444' },
        { label: 'Жиры (г)', value: fat, set: setFat, color: '#f97316' },
        { label: 'Углеводы (г)', value: carbs, set: setCarbs, color: '#3b82f6' },
        { label: 'Вода (мл)', value: water, set: setWater, color: '#06b6d4' },
      ].map((f) => (
        <div key={f.label}>
          <label className="text-xs font-medium flex items-center gap-1.5" style={{ color: 'var(--app-text)' }}>
            <span className="w-2 h-2 rounded-full" style={{ background: f.color }} />
            {f.label}
          </label>
          <input
            type="number"
            value={f.value}
            onChange={(e) => f.set(Number(e.target.value) || 0)}
            className="w-full mt-1 px-3 py-2 rounded-xl text-sm bg-transparent outline-none border border-white/[0.08]"
            style={{ color: 'var(--app-text)' }}
          />
        </div>
      ))}

      {/* Кнопка «Пересчитать» — возврат на шаг 2 */}
      <button
        onClick={() => setStep(2)}
        className="text-xs underline self-center"
        style={{ color: 'var(--app-hint)' }}
      >
        ← Изменить параметры и пересчитать
      </button>

      <motion.button
        onClick={handleSave}
        disabled={isSaving}
        className="w-full mt-2 py-3 rounded-xl text-sm font-medium text-white"
        style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
        whileTap={{ scale: 0.97 }}
      >
        {isSaving ? 'Сохранение...' : '✅ Сохранить цели'}
      </motion.button>
    </div>
  )

  // Заголовки шагов
  const stepTitles: Record<number, string> = {
    1: 'Цель',
    2: 'Параметры тела',
    3: 'Ваши КБЖУ',
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Затемнение фона */}
          <motion.div
            className="fixed inset-0"
            style={{ background: 'rgba(0,0,0,0.5)', zIndex: 50 }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={onClose}
          />
          {/* Основной лист */}
          <motion.div
            className="fixed bottom-0 left-0 right-0 rounded-t-[24px] p-4 pb-8 overflow-y-auto"
            style={{
              background: 'var(--app-bg)',
              zIndex: 51,
              borderTop: '1px solid rgba(255,255,255,0.08)',
              maxHeight: '85vh',
            }}
            initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
          >
            {/* Шапка с навигацией */}
            <div className="flex justify-between items-center mb-4">
              <div className="flex items-center gap-2">
                {step > 1 && (
                  <button onClick={() => setStep(step - 1)}>
                    <ChevronLeft size={20} style={{ color: 'var(--app-hint)' }} />
                  </button>
                )}
                <h2 className="text-lg font-bold" style={{ color: 'var(--app-text)' }}>
                  {stepTitles[step]}
                </h2>
                {/* Индикатор шагов */}
                <div className="flex gap-1 ml-2">
                  {[1, 2, 3].map((s) => (
                    <div
                      key={s}
                      className="w-2 h-2 rounded-full"
                      style={{ background: s <= step ? '#8b5cf6' : 'rgba(255,255,255,0.15)' }}
                    />
                  ))}
                </div>
              </div>
              <button onClick={onClose}>
                <X size={20} style={{ color: 'var(--app-hint)' }} />
              </button>
            </div>

            {/* Контент шага */}
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.15 }}
              >
                {step === 1 && renderStep1()}
                {step === 2 && renderStep2()}
                {step === 3 && renderStep3()}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
