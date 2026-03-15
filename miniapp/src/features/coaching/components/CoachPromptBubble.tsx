/** CoachPromptBubble — пузырь с подсказкой/инсайтом от AI-коуча. */
import { motion } from 'framer-motion'
import { Sparkles } from 'lucide-react'

interface Props {
  text: string
  action?: string
  onAction?: () => void
}

export function CoachPromptBubble({ text, action, onAction }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      // Насыщенный градиент вместо бледного — соответствует общему стилю приложения
      className="bg-gradient-to-r from-indigo-500 to-purple-600 rounded-2xl p-4 shadow-md shadow-indigo-200"
    >
      <div className="flex items-start gap-3">
        {/* Иконка коуча */}
        <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles size={16} className="text-white" />
        </div>
        <div className="flex-1">
          <p className="text-sm text-white/90 leading-relaxed">{text}</p>
          {action && onAction && (
            <button
              onClick={onAction}
              className="mt-2 text-xs font-semibold text-white hover:text-white/70 transition-colors"
            >
              {action} →
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}
