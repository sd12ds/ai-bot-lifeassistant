/**
 * Цветная боковая полоска приоритета задачи.
 * priority 1 = красный (высокий), 2 = жёлтый (обычный), 3 = зелёный (низкий).
 */
interface PriorityBadgeProps {
  priority: 1 | 2 | 3
}

const COLORS: Record<number, string> = {
  1: '#ef4444',
  2: '#f59e0b',
  3: '#22c55e',
}

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  return (
    <div
      className="absolute left-0 top-3 bottom-3 w-1 rounded-r-full"
      style={{ background: COLORS[priority] ?? COLORS[2] }}
    />
  )
}
