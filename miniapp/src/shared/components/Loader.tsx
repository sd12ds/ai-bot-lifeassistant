/**
 * Skeleton-лоадер для списка задач.
 * Показывается пока данные загружаются.
 */
export function TaskSkeletonLoader() {
  return (
    <div className="flex flex-col gap-3 px-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="rounded-[20px] p-4 border border-white/[0.06] animate-pulse"
          style={{ background: 'var(--glass-bg)', height: 80, opacity: 1 - i * 0.15 }}
        >
          <div className="flex flex-col gap-2">
            {/* Заголовок */}
            <div className="h-4 rounded-full w-3/4" style={{ background: 'rgba(255,255,255,0.08)' }} />
            {/* Подзаголовок */}
            <div className="h-3 rounded-full w-1/2" style={{ background: 'rgba(255,255,255,0.05)' }} />
          </div>
        </div>
      ))}
    </div>
  )
}
