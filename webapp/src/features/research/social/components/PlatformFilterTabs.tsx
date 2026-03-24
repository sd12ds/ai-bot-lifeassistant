/** PlatformFilterTabs — фильтр по платформе с цветами брендов. */
import type { SocialSource } from '../../../../api/social'

const PLATFORM_COLORS: Record<string, string> = {
  telegram:  'text-[#229ED9] border-[#229ED9]',
  instagram: 'text-pink-400 border-pink-400',
  vk:        'text-[#2787F5] border-[#2787F5]',
  tiktok:    'text-white border-white',
}

interface Props {
  sources: SocialSource[]
  active: string | null   // null = все
  onChange: (platform: string | null) => void
}

export function PlatformFilterTabs({ sources, active, onChange }: Props) {
  // Подсчёт по платформам
  const counts = sources.reduce<Record<string, number>>((acc, s) => {
    acc[s.platform] = (acc[s.platform] ?? 0) + 1
    return acc
  }, {})
  const platforms = Object.keys(counts)

  return (
    <div className="flex gap-2 flex-wrap">
      {/* Вкладка "Все" */}
      <button
        onClick={() => onChange(null)}
        className={`px-3 py-1 text-sm rounded-lg border transition-colors
          ${active === null
            ? 'bg-[var(--accent)]/20 text-[var(--accent)] border-[var(--accent)]'
            : 'text-[var(--text-muted)] border-[var(--border)] hover:bg-[var(--bg-hover)]'
          }`}
      >
        Все ({sources.length})
      </button>

      {platforms.map(p => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`px-3 py-1 text-sm rounded-lg border transition-colors capitalize
            ${active === p
              ? `${PLATFORM_COLORS[p] ?? 'text-white border-white'} bg-current/10`
              : 'text-[var(--text-muted)] border-[var(--border)] hover:bg-[var(--bg-hover)]'
            }`}
        >
          {p} ({counts[p]})
        </button>
      ))}
    </div>
  )
}
