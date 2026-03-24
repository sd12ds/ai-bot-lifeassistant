/** CollectionConfigPanel — настройка типа и параметров сбора. */
import { FileText, Film, MessageCircle, AtSign, Search, MapPin, Hash, BarChart2, Image, Tag } from 'lucide-react'

// Типы сбора (resultsType) — зависят от платформы
export const RESULTS_TYPES = [
  { value: 'posts',       label: 'Посты',        desc: 'Фото, видео, карусели', icon: FileText,       platforms: ['instagram', 'vk'] },
  { value: 'reels',       label: 'Reels',        desc: 'Короткие видео',        icon: Film,           platforms: ['instagram'] },
  { value: 'comments',    label: 'Комментарии',  desc: 'Комменты + ответы',     icon: MessageCircle,  platforms: ['instagram'] },
  { value: 'mentions',    label: 'Упоминания',   desc: 'Посты где отмечен',     icon: AtSign,         platforms: ['instagram'] },
  { value: 'search',      label: 'Поиск',        desc: 'По ключевому слову',    icon: Search,         platforms: ['instagram'] },
  { value: 'location',    label: 'Геолокация',   desc: 'Посты с тегом места',   icon: MapPin,         platforms: ['instagram'] },
  { value: 'hashtag',     label: 'Хэштег',       desc: 'Посты и объём хэштега', icon: Hash,           platforms: ['instagram'] },
] as const

interface ConfigPanelProps {
  platform: string
  resultsType: string
  onResultsTypeChange: (type: string) => void
  extras: {
    metrics: boolean
    media: boolean
    hashtags: boolean
    mentions: boolean
  }
  onExtrasChange: (key: string, val: boolean) => void
  limit: number
  onLimitChange: (val: number) => void
}

interface SwitchProps { checked: boolean; onChange: (v: boolean) => void }
function Switch({ checked, onChange }: SwitchProps) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative w-9 h-5 rounded-full transition-colors ${checked ? 'bg-[var(--accent)]' : 'bg-[var(--border)]'}`}
    >
      <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full transition-transform ${checked ? 'translate-x-4' : ''}`} />
    </button>
  )
}

export function CollectionConfigPanel({ platform, resultsType, onResultsTypeChange, extras, onExtrasChange, limit, onLimitChange }: ConfigPanelProps) {
  // Для Telegram — тип не выбираем (всегда posts)
  const showTypeSelector = platform !== 'telegram'
  const availableTypes = RESULTS_TYPES.filter(t => t.platforms.includes(platform as any))

  return (
    <div className="space-y-5">
      {/* Тип сбора */}
      {showTypeSelector && (
        <div>
          <p className="text-xs font-medium text-[var(--text-secondary)] mb-2">Тип сбора</p>
          <div className="space-y-1">
            {availableTypes.map(t => {
              const Icon = t.icon
              return (
                <label key={t.value} className="flex items-center gap-3 p-2 rounded-lg hover:bg-[var(--bg-hover)] cursor-pointer">
                  <input
                    type="radio"
                    name="results_type"
                    value={t.value}
                    checked={resultsType === t.value}
                    onChange={() => onResultsTypeChange(t.value)}
                    className="accent-[var(--accent)]"
                  />
                  <Icon size={14} className="text-[var(--text-muted)]" />
                  <span className="flex-1">
                    <span className="text-sm font-medium text-[var(--text-primary)]">{t.label}</span>
                    <span className="ml-2 text-xs text-[var(--text-muted)]">{t.desc}</span>
                  </span>
                </label>
              )
            })}
          </div>
        </div>
      )}

      {/* Дополнительные поля */}
      <div>
        <p className="text-xs font-medium text-[var(--text-secondary)] mb-2">Дополнительно</p>
        <div className="space-y-2">
          {[
            { key: 'metrics',  label: 'Метрики',     desc: 'Лайки, просмотры, реакции', icon: BarChart2 },
            { key: 'media',    label: 'Медиафайлы',  desc: 'URL фото и видео',           icon: Image },
            { key: 'hashtags', label: 'Хэштеги',     desc: 'Список из текста',            icon: Hash },
            { key: 'mentions', label: 'Упоминания',  desc: '@аккаунты в посте',           icon: Tag },
          ].map(({ key, label, desc, icon: Icon }) => (
            <div key={key} className="flex items-center justify-between py-1">
              <div className="flex items-center gap-2">
                <Icon size={14} className="text-[var(--text-muted)]" />
                <span className="text-sm text-[var(--text-primary)]">{label}</span>
                <span className="text-xs text-[var(--text-muted)]">— {desc}</span>
              </div>
              <Switch checked={extras[key as keyof typeof extras]} onChange={v => onExtrasChange(key, v)} />
            </div>
          ))}
        </div>
      </div>

      {/* Лимит */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-[var(--text-primary)]">Лимит за запуск</span>
        <input
          type="number"
          value={limit}
          min={1} max={500}
          onChange={e => onLimitChange(Number(e.target.value))}
          className="w-20 px-2 py-1 text-sm text-center bg-[var(--bg-hover)] border border-[var(--border)] rounded-lg text-[var(--text-primary)]"
        />
      </div>
    </div>
  )
}
