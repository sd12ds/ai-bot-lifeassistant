/**
 * Floating Action Button — градиентная кнопка "+" для создания задачи.
 * Spring-анимация при нажатии через Framer Motion.
 */
import { motion } from 'framer-motion'
import { Plus } from 'lucide-react'

interface FABProps {
  onClick: () => void
}

export function FAB({ onClick }: FABProps) {
  return (
    <motion.button
      onClick={onClick}
      className="fixed bottom-24 right-4 w-14 h-14 rounded-full flex items-center justify-center"
      style={{
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        boxShadow: 'var(--shadow-fab)',
        zIndex: 40,
      }}
      // Spring-анимация при нажатии
      whileTap={{ scale: 0.88 }}
      whileHover={{ scale: 1.08 }}
      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
      // Анимация появления
      initial={{ scale: 0, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
    >
      <Plus size={26} color="white" strokeWidth={2.5} />
    </motion.button>
  )
}
