/**
 * CheckInPage — экран чекина дня.
 * Два режима: quick (энергия + настроение + текст) и extended (+ блокеры, достижения).
 * Шкалы 1-5 соответствуют API: energy_level (1-5), mood (строковый enum).
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { ArrowLeft, ChevronDown, ChevronUp, Send } from 'lucide-react'
import { useCreateCheckIn } from '../../api/coaching'
import type { CreateCheckInDto } from '../../api/coaching'
import { GlassCard } from '../../shared/ui/GlassCard'

// 5 эмодзи для шкалы энергии 1-5
const ENERGY_LABELS = ['😴', '😔', '😐', '🙂', '🔥']
// 5 эмодзи для шкалы настроения 1-5
const MOOD_LABELS   = ['😢', '😕', '😐', '🙂', '😄']

// Маппинг числового значения настроения в строковый enum API (bad|tired|ok|good|great)
const MOOD_MAP: Record<number, string> = {
  1: 'bad',
  2: 'tired',
  3: 'ok',
  4: 'good',
  5: 'great',
}

// Компонент шкалы 1-5 с эмодзи-кнопками
function ScaleSelector({ value, onChange, labels }: { value: number; onChange: (v: number) => void; labels: string[] }) {
  return (
    <div className="flex gap-2 justify-between">
      {Array.from({ length: 5 }, (_, i) => i + 1).map(n => (
        <motion.button
          key={n}
          whileTap={{ scale: 0.85 }}
          onClick={() => onChange(n)}
          className="flex-1 aspect-square rounded-xl text-2xl flex items-center justify-center transition-all"
          style={
            value === n
              ? { background: 'rgba(99,102,241,0.35)', border: '1px solid rgba(99,102,241,0.5)', transform: 'scale(1.08)' }
              : { background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.06)' }
          }
        >
          {labels[n - 1]}
        </motion.button>
      ))}
    </div>
  )
}

export function CheckInPage() {
  const navigate = useNavigate()
  const [extended, setExtended] = useState(false)
  // Начальные значения — середина шкалы 1-5
  const [energy, setEnergy]     = useState(3)
  const [mood, setMood]         = useState(3)
  const [reflection, setReflection] = useState('')
  const [blockers, setBlockers]     = useState('')
  const [wins, setWins]             = useState('')
  // Состояние ошибки для показа пользователю
  const [submitError, setSubmitError] = useState<string | null>(null)

  const createCheckIn = useCreateCheckIn()

  const handleSubmit = () => {
    setSubmitError(null)
    // Формируем DTO строго по контракту API:
    // energy_level: 1-5, mood: строковый enum, notes (переименовано из reflection)
    const dto: CreateCheckInDto = {
      energy_level: energy,
      mood: MOOD_MAP[mood],
      notes: reflection.trim() || undefined,
      blockers: blockers.trim() || undefined,
      wins: wins.trim() || undefined,
    }
    createCheckIn.mutate(dto, {
      onSuccess: () => navigate('/coaching'),
      onError: () => setSubmitError('Не удалось сохранить чекин. Попробуй ещё раз.'),
    })
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-4 flex items-center gap-3 shrink-0">
        <button
          onClick={() => navigate('/coaching')}
          className="w-9 h-9 rounded-xl flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.06)' }}
        >
          <ArrowLeft size={20} style={{ color: 'var(--app-text)' }} />
        </button>
        <h1 className="text-xl font-black flex-1" style={{ color: 'var(--app-text)' }}>Чекин дня</h1>
        <button
          onClick={() => setExtended(v => !v)}
          className="flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-xl border border-white/[0.08]"
          style={{ background: 'rgba(255,255,255,0.05)', color: '#818cf8' }}
        >
          {extended ? <><ChevronUp size={14} /> Кратко</> : <><ChevronDown size={14} /> Подробно</>}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-28 space-y-4">
        {/* Энергия */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold" style={{ color: 'var(--app-text)' }}>⚡ Энергия</p>
            <span className="text-2xl font-black" style={{ color: '#818cf8' }}>{energy}</span>
          </div>
          <ScaleSelector value={energy} onChange={setEnergy} labels={ENERGY_LABELS} />
        </GlassCard>

        {/* Настроение */}
        <GlassCard>
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold" style={{ color: 'var(--app-text)' }}>😊 Настроение</p>
            <span className="text-2xl font-black" style={{ color: '#818cf8' }}>{mood}</span>
          </div>
          <ScaleSelector value={mood} onChange={setMood} labels={MOOD_LABELS} />
        </GlassCard>

        {/* Рефлексия (→ notes в API) */}
        <GlassCard>
          <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>💬 Как прошёл день?</p>
          <textarea
            placeholder="Напиши пару мыслей о сегодняшнем дне..."
            value={reflection}
            onChange={e => setReflection(e.target.value)}
            rows={3}
            className="w-full text-sm outline-none resize-none bg-transparent placeholder-white/30"
            style={{ color: 'var(--app-text)' }}
          />
        </GlassCard>

        {/* Расширенный режим */}
        {extended && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <GlassCard>
              <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>🚧 Блокеры</p>
              <textarea
                placeholder="Что мешало сегодня?"
                value={blockers}
                onChange={e => setBlockers(e.target.value)}
                rows={2}
                className="w-full text-sm outline-none resize-none bg-transparent placeholder-white/30"
                style={{ color: 'var(--app-text)' }}
              />
            </GlassCard>
            <GlassCard>
              <p className="font-semibold mb-2" style={{ color: 'var(--app-text)' }}>🏆 Победы</p>
              <textarea
                placeholder="Чем гордишься сегодня?"
                value={wins}
                onChange={e => setWins(e.target.value)}
                rows={2}
                className="w-full text-sm outline-none resize-none bg-transparent placeholder-white/30"
                style={{ color: 'var(--app-text)' }}
              />
            </GlassCard>
          </motion.div>
        )}
      </div>

      {/* Sticky-кнопка отправки */}
      <div
        className="fixed bottom-0 inset-x-0 px-4 py-3"
        style={{ background: 'var(--app-bg)', borderTop: '1px solid rgba(255,255,255,0.06)' }}
      >
        {/* Сообщение об ошибке */}
        {submitError && (
          <p className="text-xs text-center mb-2" style={{ color: '#f87171' }}>{submitError}</p>
        )}
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleSubmit}
          disabled={createCheckIn.isPending}
          className="w-full rounded-2xl py-4 font-bold flex items-center justify-center gap-2 disabled:opacity-40"
          style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff' }}
        >
          <Send size={18} />
          {createCheckIn.isPending ? 'Сохраняем...' : 'Сохранить чекин'}
        </motion.button>
      </div>
    </div>
  )
}
