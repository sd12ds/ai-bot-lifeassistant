/** Skeleton-компоненты для состояния загрузки Social Monitor. */

/** Пульсирующий блок-плейсхолдер */
function Pulse({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)]/40 ${className}`} />
}

/** Скелетон карточки источника (SourceCard) */
export function SourceCardSkeleton() {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-4 flex flex-col gap-3">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Pulse className="w-4 h-4 rounded-full" />
          <Pulse className="w-32 h-4" />
        </div>
        <Pulse className="w-16 h-5 rounded-full" />
      </div>
      {/* Бейджи */}
      <div className="flex gap-2">
        <Pulse className="w-20 h-5 rounded-full" />
        <Pulse className="w-14 h-5 rounded-full" />
      </div>
      {/* Sparkline */}
      <Pulse className="w-full h-8" />
      <Pulse className="w-24 h-3" />
      {/* Тайминги */}
      <div className="space-y-1">
        <Pulse className="w-36 h-3" />
        <Pulse className="w-32 h-3" />
      </div>
      {/* Кнопки */}
      <div className="flex gap-2 pt-1 border-t border-[var(--border)]">
        <Pulse className="flex-1 h-8 rounded-lg" />
        <Pulse className="flex-1 h-8 rounded-lg" />
      </div>
    </div>
  )
}

/** Скелетон карточки поста (PostCard) */
export function PostCardSkeleton() {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl overflow-hidden flex flex-col">
      {/* Шапка */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)]/60">
        <div className="flex items-center gap-2">
          <Pulse className="w-3 h-3 rounded-full" />
          <Pulse className="w-24 h-4" />
        </div>
        <Pulse className="w-20 h-3" />
      </div>
      {/* Тело: 3 колонки */}
      <div className="flex divide-x divide-[var(--border)]/60">
        {/* Превью */}
        <Pulse className="w-48 h-40 flex-shrink-0 rounded-none" />
        {/* Текст */}
        <div className="flex-1 px-4 py-3 space-y-2">
          <Pulse className="w-full h-3" />
          <Pulse className="w-4/5 h-3" />
          <Pulse className="w-3/5 h-3" />
        </div>
        {/* Статистика */}
        <div className="w-48 flex-shrink-0 px-3 py-3 space-y-2">
          <Pulse className="w-16 h-2" />
          <Pulse className="w-full h-4" />
          <Pulse className="w-full h-4" />
          <Pulse className="w-full h-4" />
          <Pulse className="w-full h-4" />
          <Pulse className="w-full h-12 mt-2" />
        </div>
      </div>
    </div>
  )
}
