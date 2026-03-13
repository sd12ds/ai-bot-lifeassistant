/**
 * Базовый glass-контейнер (glassmorphism).
 * backdrop-blur + полупрозрачный фон + тонкая рамка.
 */
import { forwardRef } from 'react'
import type { HTMLAttributes } from 'react'

interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  noPadding?: boolean
}

export const GlassCard = forwardRef<HTMLDivElement, GlassCardProps>(
  ({ className = '', noPadding, children, ...props }, ref) => (
    <div
      ref={ref}
      {...props}
      className={`
        rounded-[20px]
        backdrop-blur-xl
        border border-white/[0.08]
        ${noPadding ? '' : 'p-4'}
        ${className}
      `}
      style={{
        background: 'var(--glass-bg)',
        boxShadow: 'var(--shadow-card)',
        ...props.style,
      }}
    >
      {children}
    </div>
  )
)
GlassCard.displayName = 'GlassCard'
