/**
 * PostCard — карточка поста/рила в двухколоночном layout.
 * Левая колонка: превью + текст
 * Правая колонка: статистика + AI-анализ + кнопки действий
 */
import { useState } from 'react'
import { Eye, Heart, MessageCircle, Share2, ExternalLink, FileText, CalendarPlus, Zap, TrendingUp, Minus } from 'lucide-react'
import type { SocialPost } from '../../../../api/social'
import { PlatformIcon } from './PlatformBadge'

interface Props {
  post: SocialPost
  sourceMap?: Record<string, { platform: string; source_name: string }>
}

// Картинки проксируем через наш сервер (обход Instagram CDN CORS)
const proxyImg = (url: string) =>
  url && !url.startsWith('tg_') ? '/api/proxy/image?url=' + encodeURIComponent(url) : url

function formatNum(n?: number | null): string {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', {
    day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit',
  })
}

/** Клиентский AI-анализ на основе метрик */
function analyzePost(metrics: SocialPost['metrics'], post_type: string | null): {
  verdict: 'viral' | 'good' | 'normal' | 'low'
  label: string
  emoji: string
  reason: string
} {
  const views    = metrics?.views ?? metrics?.plays ?? 0
  const likes    = metrics?.likes ?? 0
  const comments = metrics?.comments ?? 0
  const forwards = metrics?.forwards ?? 0

  const isReel = post_type === 'reel' || post_type === 'video'

  // Engagement rate для reels = (likes + comments) / views
  const engagement = views > 0 ? (likes + comments) / views : 0

  if (isReel) {
    if (views >= 100_000 || (views >= 50_000 && engagement >= 0.03)) {
      return { verdict: 'viral', label: 'Залетел!', emoji: '🔥', reason: `${formatNum(views)} просмотров — отличный охват для рила. Engagement ${(engagement * 100).toFixed(1)}%.` }
    }
    if (views >= 10_000 && engagement >= 0.02) {
      return { verdict: 'good', label: 'Хорошие показатели', emoji: '📈', reason: `${formatNum(views)} просмотров с engagement ${(engagement * 100).toFixed(1)}% — выше среднего.` }
    }
    if (views >= 1_000) {
      return { verdict: 'normal', label: 'Средний охват', emoji: '📊', reason: `${formatNum(views)} просмотров — стандартный результат для рила.` }
    }
    return { verdict: 'low', label: 'Низкий охват', emoji: '📉', reason: `${formatNum(views)} просмотров — рил не получил широкого распространения.` }
  }

  // Для постов/каруселей ориентируемся на лайки
  const likeRate = likes
  if (likeRate >= 10_000 || forwards >= 500) {
    return { verdict: 'viral', label: 'Вирусный пост', emoji: '🔥', reason: `${formatNum(likes)} лайков — отличный результат.` }
  }
  if (likeRate >= 1_000) {
    return { verdict: 'good', label: 'Хороший пост', emoji: '📈', reason: `${formatNum(likes)} лайков — выше среднего.` }
  }
  if (likeRate >= 100) {
    return { verdict: 'normal', label: 'Обычный охват', emoji: '📊', reason: `${formatNum(likes)} лайков — стандартный результат.` }
  }
  return { verdict: 'low', label: 'Низкий охват', emoji: '📉', reason: `${formatNum(likes)} лайков — пост не получил широкого охвата.` }
}

const VERDICT_COLORS = {
  viral:  'text-orange-400 bg-orange-400/10 border-orange-400/30',
  good:   'text-green-400 bg-green-400/10 border-green-400/30',
  normal: 'text-blue-400 bg-blue-400/10 border-blue-400/30',
  low:    'text-[var(--text-muted)] bg-[var(--bg-hover)] border-[var(--border)]',
}

export function PostCard({ post, sourceMap }: Props) {
  const [expanded, setExpanded] = useState(false)
  const source   = sourceMap?.[post.source_id]
  const platform = source?.platform ?? 'instagram'
  const m        = post.metrics ?? {}
  const post_type = post.post_type ?? ''
  const isVideo  = post_type === 'reel' || post_type === 'video'
  const mediaUrls = Array.isArray(post.media_urls)
    ? post.media_urls.filter(u => u && !u.startsWith('tg_') && u.length > 10)
    : []
  const content = post.content ?? ''
  const isLong  = content.length > 180
  const analysis = analyzePost(m, post_type)

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-[var(--border)]/50">
        <div className="flex items-center gap-2">
          <PlatformIcon platform={platform} size={14} />
          <span className="text-sm font-medium">{post.author_name || source?.source_name}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-muted)]">{formatDate(post.posted_at)}</span>
          {post.post_url && (
            <a href={post.post_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink size={12} className="text-[var(--text-muted)] hover:text-[var(--accent)]" />
            </a>
          )}
        </div>
      </div>

      {/* Двухколоночный body */}
      <div className="flex gap-0">
        {/* ── Левая колонка: превью + текст ── */}
        <div className="flex-1 min-w-0 p-3 flex flex-col gap-2 border-r border-[var(--border)]/50">
          {/* Превью */}
          {mediaUrls.length > 0 && (
            isVideo ? (
              <a href={post.post_url ?? undefined} target="_blank" rel="noopener noreferrer"
                className="relative block rounded-lg overflow-hidden group flex-shrink-0">
                <img src={proxyImg(mediaUrls[0])} alt=""
                  className="w-full aspect-video object-cover bg-[var(--bg-hover)]"
                  referrerPolicy="no-referrer"
                  onError={e => (e.currentTarget.parentElement!.style.display = 'none')} />
                <div className="absolute inset-0 flex items-center justify-center bg-black/25 group-hover:bg-black/40 transition-colors">
                  <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm border border-white/40 flex items-center justify-center">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>
                  </div>
                </div>
                <span className="absolute top-1.5 right-1.5 flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-black/60 text-white text-[10px] font-medium">
                  <svg width="8" height="8" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                  Reel
                </span>
              </a>
            ) : (
              <div className={`grid gap-1 flex-shrink-0 ${mediaUrls.length === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}>
                {mediaUrls.slice(0, 2).map((url, i) => (
                  <img key={i} src={proxyImg(url)} alt=""
                    className="w-full aspect-square object-cover rounded-lg bg-[var(--bg-hover)]"
                    referrerPolicy="no-referrer"
                    onError={e => (e.currentTarget.style.display = 'none')} />
                ))}
              </div>
            )
          )}

          {/* Текст */}
          {content && (
            <div className="text-xs text-[var(--text-secondary)] leading-relaxed">
              <p>{isLong && !expanded ? content.slice(0, 180) + '…' : content}</p>
              {isLong && (
                <button onClick={() => setExpanded(!expanded)}
                  className="text-[var(--accent)] hover:underline mt-0.5">
                  {expanded ? '↑ Свернуть' : '↓ Читать далее'}
                </button>
              )}
            </div>
          )}
        </div>

        {/* ── Правая колонка: статистика + анализ + кнопки ── */}
        <div className="w-48 flex-shrink-0 p-3 flex flex-col gap-3">

          {/* Статистика */}
          <div>
            <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">Статистика</p>
            <div className="space-y-2">
              {!!m.views && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                    <Eye size={12} />
                    <span className="text-xs">Просмотры</span>
                  </div>
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{formatNum(m.views)}</span>
                </div>
              )}
              {!!m.plays && !m.views && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                    <Eye size={12} />
                    <span className="text-xs">Воспроизв.</span>
                  </div>
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{formatNum(m.plays)}</span>
                </div>
              )}
              {!!m.likes && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                    <Heart size={12} />
                    <span className="text-xs">Лайки</span>
                  </div>
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{formatNum(m.likes)}</span>
                </div>
              )}
              {!!m.comments && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                    <MessageCircle size={12} />
                    <span className="text-xs">Комменты</span>
                  </div>
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{formatNum(m.comments)}</span>
                </div>
              )}
              {!!m.forwards && (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                    <Share2 size={12} />
                    <span className="text-xs">Репосты</span>
                  </div>
                  <span className="text-sm font-semibold text-[var(--text-primary)]">{formatNum(m.forwards)}</span>
                </div>
              )}
              {/* Реакции Telegram */}
              {m.reactions && Object.keys(m.reactions).length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {Object.entries(m.reactions).slice(0, 4).map(([emoji, cnt]) => (
                    <span key={emoji} className="text-xs bg-[var(--bg-hover)] rounded px-1.5 py-0.5">
                      {emoji} {formatNum(cnt as number)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* AI-анализ */}
          <div className={`rounded-lg border px-2.5 py-2 ${VERDICT_COLORS[analysis.verdict]}`}>
            <div className="flex items-center gap-1 mb-1">
              {analysis.verdict === 'viral' ? <Zap size={11} /> :
               analysis.verdict === 'good'  ? <TrendingUp size={11} /> : <Minus size={11} />}
              <span className="text-[10px] font-bold uppercase tracking-wide">AI Анализ</span>
            </div>
            <p className="text-xs font-semibold">{analysis.emoji} {analysis.label}</p>
            <p className="text-[10px] mt-0.5 opacity-80 leading-snug">{analysis.reason}</p>
          </div>

          {/* Кнопки действий */}
          <div className="flex flex-col gap-1.5 mt-auto">
            <button
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-[var(--text-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors w-full"
              title="Скоро"
            >
              <FileText size={11} />
              Транскрибировать
            </button>
            <button
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-[var(--text-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors w-full"
              title="Скоро"
            >
              <CalendarPlus size={11} />
              В план контента
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
