/** PostCard — карточка поста с метриками и медиа-превью. */
import { useState } from 'react'
import { Eye, Heart, MessageCircle, Share2, ExternalLink } from 'lucide-react'
import type { SocialPost } from '../../../../api/social'
import { PlatformIcon } from './PlatformBadge'

interface Props {
  post: SocialPost
  sourceMap?: Record<string, { platform: string; source_name: string }>
}

function formatNum(n?: number): string {
  if (!n) return '0'
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

function formatDate(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function PostCard({ post, sourceMap }: Props) {
  const [expanded, setExpanded] = useState(false)
  const source = sourceMap?.[post.source_id]
  const platform = source?.platform ?? 'telegram'
  const m = post.metrics ?? {}
  const mediaUrls = Array.isArray(post.media_urls) ? post.media_urls.filter(u => !u.startsWith('tg_')) : []
  const content = post.content ?? ''
  const post_type = post.post_type ?? ""
  const isLong = content.length > 240

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-4 space-y-3">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <PlatformIcon platform={platform} size={14} />
          <span className="text-sm font-medium text-[var(--text-primary)]">{post.author_name || source?.source_name}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-muted)]">{formatDate(post.posted_at)}</span>
          {post.post_url && (
            <a href={post.post_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
              <ExternalLink size={12} className="text-[var(--text-muted)] hover:text-[var(--accent)]" />
            </a>
          )}
        </div>
      </div>

      {/* Контент */}
      {content && (
        <div>
          <p className="text-sm text-[var(--text-primary)] whitespace-pre-line leading-relaxed">
            {isLong && !expanded ? content.slice(0, 240) + '...' : content}
          </p>
          {isLong && (
            <button onClick={() => setExpanded(!expanded)} className="text-xs text-[var(--accent)] mt-1 hover:underline">
              {expanded ? '↑ Свернуть' : '↓ Читать далее'}
            </button>
          )}
        </div>
      )}

      {/* Медиа — Reels/Video: превью с кнопкой ▶ | Карусели/фото: сетка */}
      {mediaUrls.length > 0 && (
        post_type === 'reel' || post_type === 'video' ? (
          /* Reel/Video — одна превью с кнопкой воспроизведения */
          <a
            href={post.post_url ?? undefined}
            target="_blank"
            rel="noopener noreferrer"
            className="relative block rounded-xl overflow-hidden group"
          >
            <img
              src={'/api/proxy/image?url=' + encodeURIComponent(mediaUrls[0])}
              alt=""
              className="w-full aspect-video object-cover bg-[var(--bg-hover)]"
              referrerPolicy="no-referrer"
              onError={e => (e.currentTarget.style.display = 'none')}
            />
            {/* Overlay с кнопкой play */}
            <div className="absolute inset-0 flex items-center justify-center bg-black/30 group-hover:bg-black/50 transition-colors">
              <div className="w-14 h-14 rounded-full bg-white/20 backdrop-blur-sm border border-white/40 flex items-center justify-center">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                  <path d="M8 5v14l11-7z"/>
                </svg>
              </div>
            </div>
            {/* Бейдж Reel */}
            <div className="absolute top-2 right-2 flex items-center gap-1 px-2 py-0.5 rounded-full bg-black/60 text-white text-xs font-medium backdrop-blur-sm">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
              {post_type === 'reel' ? 'Reel' : 'Видео'}
            </div>
          </a>
        ) : (
          /* Фото / Карусель — сетка */
          <div className={`grid gap-1 ${mediaUrls.length <= 1 ? 'grid-cols-1' : mediaUrls.length === 2 ? 'grid-cols-2' : 'grid-cols-3'}`}>
            {mediaUrls.slice(0, 3).map((url, i) => (
              <img
                key={i}
                src={'/api/proxy/image?url=' + encodeURIComponent(url)}
                alt=""
                className="w-full aspect-square object-cover rounded-lg bg-[var(--bg-hover)]"
                referrerPolicy="no-referrer"
                onError={e => (e.currentTarget.style.display = 'none')}
              />
            ))}
          </div>
        )
      )}

      {/* Реакции Telegram */}
      {m.reactions && Object.keys(m.reactions).length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {Object.entries(m.reactions).slice(0, 5).map(([emoji, count]) => (
            <span key={emoji} className="text-xs bg-[var(--bg-hover)] rounded-full px-2 py-0.5">
              {emoji} {formatNum(count as number)}
            </span>
          ))}
        </div>
      )}

      {/* Метрики */}
      <div className="flex items-center gap-4 text-xs text-[var(--text-muted)] border-t border-[var(--border)] pt-2">
        {!!m.views    && <span className="flex items-center gap-1"><Eye size={11} />{formatNum(m.views)}</span>}
        {!!m.likes    && <span className="flex items-center gap-1"><Heart size={11} />{formatNum(m.likes)}</span>}
        {!!m.comments && <span className="flex items-center gap-1"><MessageCircle size={11} />{formatNum(m.comments)}</span>}
        {!!m.forwards && <span className="flex items-center gap-1"><Share2 size={11} />{formatNum(m.forwards)}</span>}
      </div>
    </div>
  )
}
