/**
 * ContentTypeFilter — таббар переключения типа контента.
 * Показывает: Все / Посты / Reels / Карусели / Видео
 * с иконками и счётчиками (опционально).
 */
import { FileText, Film, LayoutGrid, Video, Grid } from 'lucide-react'

export type PostTypeFilter = 'all' | 'image' | 'reel' | 'carousel' | 'video'

interface Option {
  value: PostTypeFilter
  label: string
  icon: typeof FileText
  apiValue: string | null   // null = не фильтруем
}

const OPTIONS: Option[] = [
  { value: 'all',      label: 'Все',       icon: Grid,       apiValue: null },
  { value: 'image',    label: 'Посты',     icon: FileText,   apiValue: 'image' },
  { value: 'reel',     label: 'Reels',     icon: Film,       apiValue: 'reel' },
  { value: 'carousel', label: 'Карусели',  icon: LayoutGrid, apiValue: 'carousel' },
  { value: 'video',    label: 'Видео',     icon: Video,      apiValue: 'video' },
]

interface Props {
  value: PostTypeFilter
  onChange: (type: PostTypeFilter) => void
  counts?: Partial<Record<PostTypeFilter, number>>   // опциональные счётчики
}

export function ContentTypeFilter({ value, onChange, counts }: Props) {
  return (
    <div className="flex gap-1 flex-wrap">
      {OPTIONS.map(opt => {
        const Icon = opt.icon
        const count = counts?.[opt.value]
        const isActive = value === opt.value

        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors
              ${isActive
                ? 'bg-[var(--accent)]/20 text-[var(--accent)] border-[var(--accent)]'
                : 'text-[var(--text-muted)] border-[var(--border)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
              }`}
          >
            <Icon size={12} />
            {opt.label}
            {count !== undefined && (
              <span className={`ml-0.5 ${isActive ? 'text-[var(--accent)]' : 'text-[var(--text-muted)]'}`}>
                ({count})
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/** Конвертирует PostTypeFilter → строку для API (или undefined) */
export function filterToApiParam(f: PostTypeFilter): string | undefined {
  return OPTIONS.find(o => o.value === f)?.apiValue ?? undefined
}

/** Бейдж типа коллекции (results_type из collection_config) для SourceCard */
const RESULTS_TYPE_LABELS: Record<string, { label: string; icon: typeof Film }> = {
  posts:       { label: 'Посты',      icon: FileText },
  reels:       { label: 'Reels',      icon: Film },
  comments:    { label: 'Комменты',   icon: FileText },
  mentions:    { label: 'Упомин.',    icon: FileText },
  search:      { label: 'Поиск',      icon: Grid },
  location:    { label: 'Геолок.',    icon: Grid },
  hashtag:     { label: 'Хэштег',     icon: Grid },
}

interface CollectionTypeBadgeProps { resultsType: string }

export function CollectionTypeBadge({ resultsType }: CollectionTypeBadgeProps) {
  const cfg = RESULTS_TYPE_LABELS[resultsType] ?? { label: resultsType, icon: Grid }
  const Icon = cfg.icon
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-[var(--accent)]/10 text-[var(--accent)]">
      <Icon size={10} />
      {cfg.label}
    </span>
  )
}
