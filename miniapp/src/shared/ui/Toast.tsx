/**
 * Встроенный toast-компонент для уведомлений.
 * Не использует Telegram.WebApp.showAlert() — не сбивает масштаб.
 */
import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface ToastProps {
  /** Текст уведомления */
  message: string | null
  /** Закрыть toast */
  onClose: () => void
  /** Время показа (мс), по умолчанию 2500 */
  duration?: number
  /** Тип уведомления: success (по умолчанию) или error */
  type?: 'success' | 'error'
}

export function Toast({ message, onClose, duration = 2500, type = 'success' }: ToastProps) {
  // Автоматически скрываем через duration мс
  useEffect(() => {
    if (!message) return
    const timer = setTimeout(onClose, duration)
    return () => clearTimeout(timer)
  }, [message, onClose, duration])

  // Цвет фона зависит от типа уведомления
  const background =
    type === 'error' ? 'rgba(239,68,68,0.95)' : 'rgba(34,197,94,0.95)'

  return (
    <AnimatePresence>
      {message && (
        <motion.div
          className="fixed top-6 left-4 right-4 flex justify-center"
          style={{ zIndex: 100 }}
          initial={{ opacity: 0, y: -30 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ type: 'spring', damping: 20, stiffness: 300 }}
        >
          <div
            className="px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg"
            style={{
              background,
              color: '#fff',
              backdropFilter: 'blur(8px)',
            }}
          >
            {message}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
