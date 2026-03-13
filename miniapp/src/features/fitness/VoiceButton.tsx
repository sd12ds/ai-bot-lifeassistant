/**
 * Floating-кнопка голосового ввода для ActiveWorkout.
 * Записывает аудио через MediaRecorder, отправляет на бэкенд для транскрипции,
 * возвращает распознанный интент (add_set, add_exercise, rest_timer, finish).
 */
import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Mic, MicOff, Loader2 } from 'lucide-react'

/** Интент, возвращаемый бэкендом */
export interface VoiceIntent {
  text: string
  intent: 'add_set' | 'add_exercise' | 'rest_timer' | 'finish' | 'unknown'
  params: Record<string, any>
}

interface VoiceButtonProps {
  /** Колбэк при успешном распознавании интента */
  onIntent: (result: VoiceIntent) => void
  /** URL API для транскрипции */
  apiUrl?: string
  /** Отключена ли кнопка */
  disabled?: boolean
}

/** Состояния кнопки */
type VoiceState = 'idle' | 'recording' | 'processing'

export function VoiceButton({ onIntent, disabled = false }: VoiceButtonProps) {
  const [state, setState] = useState<VoiceState>('idle')
  const [toast, setToast] = useState<string | null>(null) // Тост с распознанным текстом
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Показать тост на 3 секунды
  const showToast = useCallback((text: string) => {
    setToast(text)
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current)
    toastTimerRef.current = setTimeout(() => setToast(null), 3000)
  }, [])

  // Отправить аудио на бэкенд
  const sendAudio = useCallback(async (audioBlob: Blob) => {
    setState('processing')
    try {
      const formData = new FormData()
      formData.append('file', audioBlob, 'voice.webm')

      // Получаем initData для авторизации
      const initData = window.Telegram?.WebApp?.initData || ''

      const resp = await fetch('/api/voice/transcribe', {
        method: 'POST',
        headers: { 'X-Init-Data': initData },
        body: formData,
      })

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`)
      }

      const result: VoiceIntent = await resp.json()

      // Показываем распознанный текст
      if (result.text) {
        showToast(`🎙️ ${result.text}`)
      }

      // Передаём интент наверх
      onIntent(result)
    } catch (err) {
      console.error('Ошибка голосового ввода:', err)
      showToast('❌ Не удалось распознать')
    } finally {
      setState('idle')
    }
  }, [onIntent, showToast])

  // Начать запись
  const startRecording = useCallback(async () => {
    try {
      // Запрашиваем доступ к микрофону
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })

      // Выбираем поддерживаемый формат
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/mp4'

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      // Собираем чанки аудио
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      // По завершении записи — отправляем
      recorder.onstop = () => {
        // Останавливаем все треки микрофона
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: mimeType })
        if (blob.size > 100) {
          sendAudio(blob)
        } else {
          setState('idle')
        }
      }

      recorder.start()
      setState('recording')

      // Haptic feedback при начале записи
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('light')
    } catch (err) {
      console.error('Нет доступа к микрофону:', err)
      showToast('🎙️ Разреши доступ к микрофону')
      setState('idle')
    }
  }, [sendAudio, showToast])

  // Остановить запись
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
      // Haptic feedback при остановке
      window.Telegram?.WebApp?.HapticFeedback?.impactOccurred('medium')
    }
  }, [])

  // Обработка нажатия
  const handlePress = useCallback(() => {
    if (disabled) return
    if (state === 'idle') {
      startRecording()
    } else if (state === 'recording') {
      stopRecording()
    }
    // Если processing — игнорируем
  }, [state, disabled, startRecording, stopRecording])

  return (
    <>
      {/* Floating-кнопка микрофона */}
      <motion.button
        onClick={handlePress}
        disabled={disabled || state === 'processing'}
        className="fixed z-40 flex items-center justify-center rounded-full shadow-lg"
        style={{
          bottom: 88, // Над BottomNav
          right: 16,
          width: 52,
          height: 52,
          background: state === 'recording'
            ? 'linear-gradient(135deg, #ef4444, #dc2626)' // Красный при записи
            : state === 'processing'
              ? 'rgba(99,102,241,0.3)' // Полупрозрачный при обработке
              : 'linear-gradient(135deg, #6366f1, #8b5cf6)', // Фиолетовый по умолчанию
          opacity: disabled ? 0.4 : 1,
        }}
        // Пульсация при записи
        animate={state === 'recording' ? {
          scale: [1, 1.1, 1],
          boxShadow: [
            '0 0 0 0 rgba(239,68,68,0.4)',
            '0 0 0 12px rgba(239,68,68,0)',
            '0 0 0 0 rgba(239,68,68,0.4)',
          ],
        } : { scale: 1 }}
        transition={state === 'recording' ? { duration: 1.2, repeat: Infinity } : {}}
        whileTap={{ scale: 0.9 }}
      >
        {state === 'processing' ? (
          <Loader2 size={22} className="animate-spin" style={{ color: 'white' }} />
        ) : state === 'recording' ? (
          <MicOff size={22} style={{ color: 'white' }} />
        ) : (
          <Mic size={22} style={{ color: 'white' }} />
        )}
      </motion.button>

      {/* Тост с распознанным текстом */}
      <AnimatePresence>
        {toast && (
          <motion.div
            className="fixed z-50 left-4 right-4 px-4 py-3 rounded-2xl text-sm font-medium text-center"
            style={{
              bottom: 148, // Над кнопкой
              background: 'rgba(0,0,0,0.85)',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.1)',
            }}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
          >
            {toast}
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
