/**
 * OnboardingPage — 4-шаговый онбординг коучинга.
 * Свайпаемые слайды с анимацией и прогресс-индикатором.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import { useAdvanceOnboarding, useCompleteOnboarding } from '../../api/coaching'

interface Step {
  emoji: string
  title: string
  description: string
  cta: string
}

const STEPS: Step[] = [
  {
    emoji: '🧭',
    title: 'Твой AI-коуч',
    description: 'Я помогу тебе ставить цели, отслеживать прогресс и развивать привычки. Каждый день — маленький шаг к большому результату.',
    cta: 'Отлично, давай',
  },
  {
    emoji: '🎯',
    title: 'Цели со смыслом',
    description: 'Не просто «хочу в зал», а «я хочу чувствовать себя энергичным, чтобы успевать больше». Мы разберём твоё «зачем».',
    cta: 'Понятно',
  },
  {
    emoji: '🔥',
    title: 'Привычки — основа',
    description: 'Маленькие ежедневные действия приводят к большим переменам. Я помогу отследить серию и не потерять темп.',
    cta: 'Звучит хорошо',
  },
  {
    emoji: '💬',
    title: 'Ежедневный чекин',
    description: 'Пара минут в конце дня — и я смогу давать точные инсайты и поддержку именно тогда, когда это нужно.',
    cta: 'Начать',
  },
]

export function OnboardingPage() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [direction, setDirection] = useState(1) // 1=вперёд, -1=назад

  const advanceOnboarding = useAdvanceOnboarding()
  const completeOnboarding = useCompleteOnboarding()

  const current = STEPS[step]
  const isLast = step === STEPS.length - 1

  const handleNext = () => {
    if (isLast) {
      // Завершаем онбординг и переходим на дашборд
      completeOnboarding.mutate(undefined, {
        onSuccess: () => navigate('/coaching'),
      })
      return
    }
    advanceOnboarding.mutate(String(step + 1))
    setDirection(1)
    setStep(s => s + 1)
  }

  const handleBack = () => {
    if (step === 0) return
    setDirection(-1)
    setStep(s => s - 1)
  }

  const variants = {
    enter: (d: number) => ({ x: d > 0 ? 60 : -60, opacity: 0 }),
    center: { x: 0, opacity: 1 },
    exit: (d: number) => ({ x: d > 0 ? -60 : 60, opacity: 0 }),
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Прогресс-индикатор */}
      <div className="flex gap-1.5 px-6 pt-12 pb-6 shrink-0">
        {STEPS.map((_, i) => (
          <div
            key={i}
            className="h-1 flex-1 rounded-full transition-all duration-300"
            style={{
              background: i <= step ? '#6366f1' : 'rgba(255,255,255,0.1)',
            }}
          />
        ))}
      </div>

      {/* Контент слайда */}
      <div className="flex-1 flex flex-col items-center justify-center px-8 overflow-hidden">
        <AnimatePresence custom={direction} mode="wait">
          <motion.div
            key={step}
            custom={direction}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="text-center"
          >
            <div className="text-7xl mb-6">{current.emoji}</div>
            <h2 className="text-2xl font-black mb-4" style={{ color: 'var(--app-text)' }}>{current.title}</h2>
            <p className="text-base leading-relaxed max-w-xs mx-auto" style={{ color: 'var(--app-hint)' }}>
              {current.description}
            </p>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Кнопки навигации */}
      <div className="px-6 pb-12 space-y-3 shrink-0">
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleNext}
          disabled={completeOnboarding.isPending}
          className="w-full rounded-2xl py-4 font-bold text-base flex items-center justify-center gap-2 disabled:opacity-40"
          style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
        >
          {current.cta}
          {!isLast && <ChevronRight size={20} />}
        </motion.button>

        {step > 0 && (
          <button
            onClick={handleBack}
            className="w-full text-sm py-2"
            style={{ color: 'var(--app-hint)' }}
          >
            Назад
          </button>
        )}

        {step === 0 && (
          <button
            onClick={() => completeOnboarding.mutate(undefined, { onSuccess: () => navigate('/coaching') })}
            className="w-full text-sm py-2"
            style={{ color: 'var(--app-hint)' }}
          >
            Пропустить
          </button>
        )}
      </div>
    </div>
  )
}
