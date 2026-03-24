/**
 * PostCard — двухколоночная карточка.
 * Левая: превью (маленькое) + текст под ним.
 * Правая: статистика (всегда), AI анализ, кнопки.
 */
import { useState } from 'react'
import { Eye, Heart, MessageCircle, Share2, ExternalLink, FileText, CalendarPlus, Zap, TrendingUp, Minus } from 'lucide-react'
import type { SocialPost } from '../../../../api/social'
import { PlatformIcon } from './PlatformBadge'

interface Props {
  post: SocialPost
  sourceMap?: Record<string, { platform: string; source_name: string }>
}

const proxyImg = (url: string) =>
  url && !url.startsWith('tg_') ? '/api/proxy/image?url=' + encodeURIComponent(url) : url

function fmtNum(n?: number | null): string {
  if (n === undefined || n === null) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function analyze(m: SocialPost['metrics'], post_type: string) {
  const views = m?.views ?? m?.plays ?? 0
  const likes = m?.likes ?? 0
  const comments = m?.comments ?? 0
  const isReel = post_type === 'reel' || post_type === 'video'
  const eng = views > 0 ? (likes + comments) / views : 0

  if (isReel) {
    if (views >= 100_000 || (views >= 50_000 && eng >= 0.03))
      return { verdict: 'viral' as const, label: 'Залетел!', emoji: '🔥', text: `${fmtNum(views)} просмотров — отличный охват. Engagement ${(eng * 100).toFixed(1)}%.` }
    if (views >= 10_000 && eng >= 0.02)
      return { verdict: 'good' as const, label: 'Хорошие показатели', emoji: '📈', text: `${fmtNum(views)} просмотров, engagement ${(eng * 100).toFixed(1)}% — выше среднего.` }
    if (views >= 1_000)
      return { verdict: 'normal' as const, label: 'Средний охват', emoji: '📊', text: `${fmtNum(views)} просмотров — стандартный результат.` }
    return { verdict: 'low' as const, label: 'Низкий охват', emoji: '📉', text: `${fmtNum(views)} просмотров — рил не набрал охвата.` }
  }
  if (likes >= 10_000) return { verdict: 'viral' as const, label: 'Вирусный', emoji: '🔥', text: `${fmtNum(likes)} лайков — отличный результат.` }
  if (likes >= 1_000)  return { verdict: 'good' as const,  label: 'Хорошо', emoji: '📈', text: `${fmtNum(likes)} лайков — выше среднего.` }
  if (likes >= 100)    return { verdict: 'normal' as const, label: 'Обычно', emoji: '📊', text: `${fmtNum(likes)} лайков — стандарт.` }
  return { verdict: 'low' as const, label: 'Низкий охват', emoji: '📉', text: `${fmtNum(likes)} лайков.` }
}

const VERDICT_CLS = {
  viral:  'border-orange-500/40 bg-orange-500/8',
  good:   'border-green-500/40 bg-green-500/8',
  normal: 'border-blue-500/30 bg-blue-500/8',
  low:    'border-[var(--border)] bg-[var(--bg-hover)]',
}
const VERDICT_TEXT = {
  viral: 'text-orange-400', good: 'text-green-400', normal: 'text-blue-400', low: 'text-[var(--text-muted)]',
}

export function PostCard({ post, sourceMap }: Props) {
  const [expanded, setExpanded] = useState(false)
  const source    = sourceMap?.[post.source_id]
  const platform  = source?.platform ?? 'instagram'
  const m         = post.metrics ?? {}
  const post_type = post.post_type ?? ''
  const isVideo   = post_type === 'reel' || post_type === 'video'
  const mediaUrls = Array.isArray(post.media_urls)
    ? post.media_urls.filter(u => u && !u.startsWith('tg_') && u.length > 10)
    : []
  const content = post.content ?? ''
  const isLong  = content.length > 200
  const ai      = analyze(m, post_type)

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl overflow-hidden">
      {/* Шапка */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--border)]/60">
        <div className="flex items-center gap-2">
          <PlatformIcon platform={platform} size={13} />
          <span className="text-sm font-medium">{post.author_name || source?.source_name}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--text-muted)]">{fmtDate(post.posted_at)}</span>
          {post.post_url && (
            <a href={post.post_url} target="_blank" rel="noopener noreferrer">
              <ExternalLink size={11} className="text-[var(--text-muted)] hover:text-[var(--accent)]" />
            </a>
          )}
        </div>
      </div>

      {/* Тело: две колонки */}
      <div className="flex divide-x divide-[var(--border)]/60">

        {/* ── Левая: превью маленькое + текст ── */}
        <div className="flex-1 min-w-0 p-3 flex flex-col gap-2">

          {/* Превью — ограниченная высота */}
          {mediaUrls.length > 0 && (
            isVideo ? (
              <a href={post.post_url ?? undefined} target="_blank" rel="noopener noreferrer"
                className="relative block rounded-lg overflow-hidden group self-start w-full max-h-44 flex-shrink-0">
                <img
                  src={proxyImg(mediaUrls[0])} alt=""
                  className="w-full max-h-44 object-cover bg-[var(--bg-hover)]"
                  style={{ aspectRatio: '16/9' }}
                  referrerPolicy="no-referrer"
                  onError={e => { (e.currentTarget.closest('a') as HTMLElement).style.display = 'none' }}
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/40 transition-colors">
                  <div className="w-9 h-9 rounded-full bg-white/20 backdrop-blur-sm border border-white/40 flex items-center justify-center">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>
                  </div>
                </div>
                <span className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/60 text-white text-[10px] font-medium flex items-center gap-0.5">
                  <svg width="7" height="7" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>Reel
                </span>
              </a>
            ) : (
              <div className={`grid gap-1 flex-shrink-0 ${mediaUrls.length === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}>
                {mediaUrls.slice(0, 2).map((url, i) => (
                  <img key={i} src={proxyImg(url)} alt=""
                    className="w-full aspect-square object-cover rounded-lg bg-[var(--bg-hover)] max-h-40"
                    referrerPolicy="no-referrer"
                    onError={e => (e.currentTarget.style.display = 'none')} />
                ))}
              </div>
            )
          )}

          {/* Текст */}
          {content && (
            <div className="text-xs text-[var(--text-secondary)] leading-relaxed">
              <p>{isLong && !expanded ? content.slice(0, 200) + '…' : content}</p>
              {isLong && (
                <button onClick={() => setExpanded(!expanded)} className="text-[var(--accent)] hover:underline mt-0.5">
                  {expanded ? '↑ Свернуть' : '↓ Читать далее'}
                </button>
              )}
            </div>
          )}
        </div>

        {/* ── Правая: статистика + AI + кнопки ── */}
        <div className="w-44 flex-shrink-0 p-3 flex flex-col gap-3">

          {/* Статистика — всегда показываем все поля */}
          <div>
            <p className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wide mb-2">Статистика</p>
            <div className="space-y-1.5">
              {[
                { icon: Eye,            label: 'Просмотры', val: m.views ?? m.plays },
                { icon: Heart,          label: 'Лайки',     val: m.likes },
                { icon: MessageCircle,  label: 'Комменты',  val: m.comments },
                { icon: Share2,         label: 'Репосты',   val: m.forwards },
              ].map(({ icon: Icon, label, val }) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 text-[var(--text-muted)]">
                    <Icon size={11} />
                    <span className="text-xs text-[var(--text-secondary)]">{label}</span>
                  </div>
                  <span className={`text-sm font-semibold ${!val ? 'text-[var(--text-muted)]' : 'text-[var(--text-primary)]'}`}>
                    {fmtNum(val ?? 0)}
                  </span>
                </div>
              ))}
              {/* Реакции Telegram */}
              {m.reactions && Object.keys(m.reactions).length > 0 && (
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {Object.entries(m.reactions).slice(0, 3).map(([emoji, cnt]) => (
                    <span key={emoji} className="text-[10px] bg-[var(--bg-hover)] rounded px-1.5 py-0.5">
                      {emoji} {fmtNum(cnt as number)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* AI анализ */}
          <div className={`rounded-lg border p-2 ${VERDICT_CLS[ai.verdict]}`}>
            <div className={`flex items-center gap-1 mb-0.5 ${VERDICT_TEXT[ai.verdict]}`}>
              {ai.verdict === 'viral' ? <Zap size={10}/> : ai.verdict === 'good' ? <TrendingUp size={10}/> : <Minus size={10}/>}
              <span className="text-[9px] font-bold uppercase tracking-wide">AI Анализ</span>
            </div>
            <p className={`text-xs font-semibold ${VERDICT_TEXT[ai.verdict]}`}>{ai.emoji} {ai.label}</p>
            <p className="text-[10px] text-[var(--text-muted)] mt-0.5 leading-snug">{ai.text}</p>
          </div>

          {/* Кнопки */}
          <div className="flex flex-col gap-1.5">
            <button className="flex items-center gap-1.5 px-2 py-1.5 text-xs text-[var(--text-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors">
              <FileText size={10} /> Транскрибировать
            </button>
            <button className="flex items-center gap-1.5 px-2 py-1.5 text-xs text-[var(--text-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors">
              <CalendarPlus size={10} /> В план контента
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
