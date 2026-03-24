/** PlatformBadge — иконка + цветной pill для платформы. */
import { Send, Instagram, Users, Music } from 'lucide-react'

const PLATFORM_CONFIG = {
  telegram:  { label: 'Telegram',  bg: 'bg-[#229ED9]/15', text: 'text-[#229ED9]',  Icon: Send },
  instagram: { label: 'Instagram', bg: 'bg-pink-500/15',   text: 'text-pink-400',   Icon: Instagram },
  vk:        { label: 'VK',        bg: 'bg-[#2787F5]/15', text: 'text-[#2787F5]',  Icon: Users },
  tiktok:    { label: 'TikTok',    bg: 'bg-white/10',     text: 'text-white',       Icon: Music },
} as const

type Platform = keyof typeof PLATFORM_CONFIG

interface Props {
  platform: string
  showLabel?: boolean
  size?: 'sm' | 'md'
}

export function PlatformBadge({ platform, showLabel = true, size = 'sm' }: Props) {
  const cfg = PLATFORM_CONFIG[platform as Platform] ?? PLATFORM_CONFIG.telegram
  const Icon = cfg.Icon
  const iconSize = size === 'sm' ? 12 : 16
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.text}`}>
      <Icon size={iconSize} />
      {showLabel && cfg.label}
    </span>
  )
}

/** Только иконка платформы без фона (для заголовков). */
export function PlatformIcon({ platform, size = 18 }: { platform: string; size?: number }) {
  const cfg = PLATFORM_CONFIG[platform as Platform] ?? PLATFORM_CONFIG.telegram
  const Icon = cfg.Icon
  return <Icon size={size} className={cfg.text} />
}
