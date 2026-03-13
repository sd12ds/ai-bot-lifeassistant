/**
 * Тег-пилюля для отображения тегов задачи.
 */
interface TagPillProps {
  label: string
}

export function TagPill({ label }: TagPillProps) {
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
      style={{
        background: 'rgba(99,102,241,0.15)',
        color: '#a5b4fc',
        border: '1px solid rgba(99,102,241,0.2)',
      }}
    >
      {label}
    </span>
  )
}
