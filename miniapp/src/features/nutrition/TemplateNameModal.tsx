/**
 * Модальное окно для ввода имени шаблона.
 * Заменяет window.prompt() — стилизовано под MiniApp.
 * font-size >= 16px чтобы iOS не зумил при фокусе.
 */
import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

interface TemplateNameModalProps {
  /** Модал открыт */
  open: boolean
  /** Идёт сохранение */
  loading?: boolean
  /** Закрыть модал */
  onClose: () => void
  /** Подтвердить имя */
  onConfirm: (name: string) => void
}

export function TemplateNameModal({ open, loading, onClose, onConfirm }: TemplateNameModalProps) {
  // Локальный стейт имени шаблона
  const [name, setName] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  // Сбрасываем имя при открытии и фокусируем инпут
  useEffect(() => {
    if (open) {
      setName('')
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [open])

  // Blur инпута и закрытие — убираем клавиатуру перед закрытием модала
  const handleClose = () => {
    inputRef.current?.blur()
    // Небольшая задержка чтобы клавиатура успела скрыться
    setTimeout(() => onClose(), 50)
  }

  // Обработчик подтверждения
  const handleSubmit = () => {
    const trimmed = name.trim()
    if (trimmed && !loading) {
      inputRef.current?.blur()
      onConfirm(trimmed)
    }
  }

  // Отправка по Enter
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit()
    if (e.key === 'Escape') handleClose()
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Затемнение */}
          <motion.div
            className="fixed inset-0"
            style={{ background: 'rgba(0,0,0,0.6)', zIndex: 60 }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={handleClose}
          />
          {/* Модал по центру */}
          <motion.div
            className="fixed inset-0 flex items-center justify-center px-8"
            style={{ zIndex: 61 }}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: 'spring', damping: 25, stiffness: 400 }}
          >
            <div
              className="w-full max-w-xs rounded-2xl p-5"
              style={{ background: 'var(--app-card-bg, #1e1e2e)', border: '1px solid rgba(255,255,255,0.1)' }}
            >
              {/* Заголовок */}
              <h3
                className="text-base font-bold mb-3 text-center"
                style={{ color: 'var(--app-text)' }}
              >
                📋 Сохранить как шаблон
              </h3>

              {/* Поле ввода имени — font-size: 16px минимум чтобы iOS не зумил */}
              <input
                ref={inputRef}
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Название шаблона..."
                maxLength={50}
                className="w-full px-3 py-2.5 rounded-xl outline-none"
                style={{
                  fontSize: '16px',
                  background: 'rgba(255,255,255,0.06)',
                  color: 'var(--app-text)',
                  border: '1px solid rgba(255,255,255,0.1)',
                }}
              />

              {/* Кнопки */}
              <div className="flex gap-2 mt-4">
                {/* Отмена */}
                <button
                  onClick={handleClose}
                  disabled={loading}
                  className="flex-1 py-2.5 rounded-xl text-sm font-medium"
                  style={{ color: 'var(--app-hint)', background: 'rgba(255,255,255,0.06)' }}
                >
                  Отмена
                </button>
                {/* Сохранить */}
                <button
                  onClick={handleSubmit}
                  disabled={!name.trim() || loading}
                  className="flex-1 py-2.5 rounded-xl text-sm font-medium text-white"
                  style={{
                    background: name.trim() && !loading
                      ? 'linear-gradient(135deg, #6366f1, #8b5cf6)'
                      : 'rgba(99,102,241,0.3)',
                    opacity: name.trim() && !loading ? 1 : 0.5,
                  }}
                >
                  {loading ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
