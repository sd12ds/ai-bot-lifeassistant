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
          className={`flex-1 aspect-square rounded-xl text-2xl flex items-center justify-center transition-all ${
            value === n ? 'bg-indigo-500 shadow-sm scale-110' : 'bg-gray-100'
          }`}
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
    <div className="min-h-screen bg-gray-50 pb-32">
      {/* Шапка */}
      <div className="px-4 pt-6 pb-4 flex items-center gap-3">
        <button onClick={() => navigate('/coaching')} className="text-gray-500">
          <ArrowLeft size={22} />
        </button>
        <h1 className="text-xl font-black text-gray-900 flex-1">Чекин дня</h1>
        <button
          onClick={() => setExtended(v => !v)}
          className="flex items-center gap-1 text-xs text-indigo-500 font-medium"
        >
          {extended ? <><ChevronUp size={14} /> Кратко</> : <><ChevronDown size={14} /> Подробно</>}
        </button>
      </div>

      <div className="px-4 space-y-5">
        {/* Энергия */}
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold text-gray-800">⚡ Энергия</p>
            <span className="text-2xl font-black text-indigo-500">{energy}</span>
          </div>
          <ScaleSelector value={energy} onChange={setEnergy} labels={ENERGY_LABELS} />
        </div>

        {/* Настроение */}
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <p className="font-semibold text-gray-800">😊 Настроение</p>
            <span className="text-2xl font-black text-indigo-500">{mood}</span>
          </div>
          <ScaleSelector value={mood} onChange={setMood} labels={MOOD_LABELS} />
        </div>

        {/* Рефлексия (→ notes в API) */}
        <div className="bg-white rounded-2xl p-4 shadow-sm">
          <p className="font-semibold text-gray-800 mb-2">💬 Как прошёл день?</p>
          <textarea
            placeholder="Напиши пару мыслей о сегодняшнем дне..."
            value={reflection}
            onChange={e => setReflection(e.target.value)}
            rows={3}
            className="w-full text-sm text-gray-700 placeholder-gray-400 outline-none resize-none"
          />
        </div>

        {/* Расширенный режим */}
        {extended && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <div className="bg-white rounded-2xl p-4 shadow-sm">
              <p className="font-semibold text-gray-800 mb-2">🚧 Блокеры</p>
              <textarea
                placeholder="Что мешало сегодня?"
                value={blockers}
                onChange={e => setBlockers(e.target.value)}
                rows={2}
                className="w-full text-sm text-gray-700 placeholder-gray-400 outline-none resize-none"
              />
            </div>
            <div className="bg-white rounded-2xl p-4 shadow-sm">
              <p className="font-semibold text-gray-800 mb-2">🏆 Победы</p>
              <textarea
                placeholder="Чем гордишься сегодня?"
                value={wins}
                onChange={e => setWins(e.target.value)}
                rows={2}
                className="w-full text-sm text-gray-700 placeholder-gray-400 outline-none resize-none"
              />
            </div>
          </motion.div>
        )}
      </div>

      {/* Sticky-кнопка отправки */}
      <div className="fixed bottom-0 inset-x-0 bg-white border-t border-gray-100 px-4 py-3">
        {/* Сообщение об ошибке */}
        {submitError && (
          <p className="text-red-500 text-xs text-center mb-2">{submitError}</p>
        )}
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleSubmit}
          disabled={createCheckIn.isPending}
          className="w-full bg-indigo-600 text-white rounded-2xl py-4 font-bold flex items-center justify-center gap-2 disabled:opacity-50 shadow-lg shadow-indigo-200"
        >
          <Send size={18} />
          {createCheckIn.isPending ? 'Сохраняем...' : 'Сохранить чекин'}
        </motion.button>
      </div>
    </div>
  )
}
