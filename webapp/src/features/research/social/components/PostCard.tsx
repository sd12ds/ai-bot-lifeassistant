/**
 * PostCard — 3 колонки:
 * [квадратное превью] | [текст] | [статистика + AI + кнопки]
 */
import { useState } from 'react'
import { Eye, Heart, MessageCircle, Share2, ExternalLink, FileText, CalendarPlus, Zap, TrendingUp, Minus, Loader2 } from 'lucide-react'
import type { SocialPost } from '../../../../api/social'
import { transcribePost } from '../../../../api/social'
import { TranscriptModal } from './TranscriptModal'
import { PlatformIcon } from './PlatformBadge'

interface Props {
  post: SocialPost
  sourceMap?: Record<string, { platform: string; source_name: string }>
}

const proxyImg = (url: string) =>
  url && !url.startsWith('tg_') ? '/api/proxy/image?url=' + encodeURIComponent(url) : url

function fmtNum(n?: number | null): string {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function analyze(m: SocialPost['metrics'], type: string) {
  const views = m?.views ?? m?.plays ?? 0
  const likes = m?.likes ?? 0
  const cmts  = m?.comments ?? 0
  const isV   = type === 'reel' || type === 'video'
  const eng   = views > 0 ? (likes + cmts) / views : 0
  if (isV) {
    if (views >= 100_000 || (views >= 50_000 && eng >= 0.03)) return { v: 'viral', label: 'Залетел!',             emoji: '🔥', text: `${fmtNum(views)} просмотров, eng ${(eng*100).toFixed(1)}% — отличный охват.` }
    if (views >= 10_000  && eng >= 0.02)                       return { v: 'good',  label: 'Хорошие показатели', emoji: '📈', text: `${fmtNum(views)} просмотров, выше среднего.` }
    if (views >= 1_000)                                         return { v: 'ok',    label: 'Средний охват',      emoji: '📊', text: `${fmtNum(views)} просмотров — стандарт.` }
    return { v: 'low', label: 'Низкий охват', emoji: '📉', text: `${fmtNum(views)} просмотров — рил не набрал охвата.` }
  }
  if (likes >= 10_000) return { v: 'viral', label: 'Вирусный',  emoji: '🔥', text: `${fmtNum(likes)} лайков — отлично.` }
  if (likes >= 1_000)  return { v: 'good',  label: 'Хорошо',    emoji: '📈', text: `${fmtNum(likes)} лайков — выше среднего.` }
  if (likes >= 100)    return { v: 'ok',    label: 'Обычно',    emoji: '📊', text: `${fmtNum(likes)} лайков.` }
  return { v: 'low', label: 'Низкий охват', emoji: '📉', text: `${fmtNum(likes)} лайков.` }
}

const V_BORDER = { viral: 'border-orange-500/50', good: 'border-green-500/40', ok: 'border-blue-500/30', low: 'border-[var(--border)]' }
const V_BG     = { viral: 'bg-orange-500/10',     good: 'bg-green-500/8',      ok: 'bg-blue-500/8',     low: 'bg-[var(--bg-hover)]' }
const V_TEXT   = { viral: 'text-orange-400',       good: 'text-green-400',      ok: 'text-blue-400',     low: 'text-[var(--text-muted)]' }

export function PostCard({ post, sourceMap }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [transcript, setTranscript] = useState<string | null>(post.transcript ?? null)
  const [showModal, setShowModal] = useState(false)
  const [transcribeError, setTranscribeError] = useState('')
  const source   = sourceMap?.[post.source_id]
  const platform = source?.platform ?? 'instagram'
  const m        = post.metrics ?? {}
  const type     = post.post_type ?? ''
  const isVideo  = type === 'reel' || type === 'video'
  const media    = Array.isArray(post.media_urls) ? post.media_urls.filter(u => u && !u.startsWith('tg_') && u.length > 10) : []
  const content  = post.content ?? ''
  const ai       = analyze(m, type)
  const isLong   = content.length > 220

  return (
    <>
    <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl overflow-hidden flex flex-col">

      {/* Шапка */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border)]/60">
        <div className="flex items-center gap-2">
          <PlatformIcon platform={platform} size={13} />
          <span className="text-sm font-medium text-[var(--text-primary)]">{post.author_name || source?.source_name}</span>
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

      {/* Тело: 3 колонки */}
      <div className="flex divide-x divide-[var(--border)]/60 flex-1">

        {/* ── Колонка 1: квадратное превью ── */}
        <div className="w-48 flex-shrink-0 relative overflow-hidden">
          {media.length > 0 ? (
            isVideo ? (
              <a href={post.post_url ?? undefined} target="_blank" rel="noopener noreferrer"
                className="absolute inset-0 block group">
                <img
                  src={proxyImg(media[0])} alt=""
                  className="w-full h-full object-cover"
                  referrerPolicy="no-referrer"
                  onError={e => { const el = e.currentTarget.closest('a') as HTMLElement; if (el) el.style.display = 'none' }}
                />
                {/* Play overlay */}
                <div className="absolute inset-0 flex items-center justify-center bg-black/25 group-hover:bg-black/45 transition-colors">
                  <div className="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm border border-white/40 flex items-center justify-center">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg>
                  </div>
                </div>
                {/* Reel badge */}
                <span className="absolute bottom-1.5 left-1.5 flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-black/65 text-white text-[9px] font-semibold backdrop-blur-sm">
                  <svg width="7" height="7" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
                  Reel
                </span>
              </a>
            ) : (
              <img
                src={proxyImg(media[0])} alt=""
                className="absolute inset-0 w-full h-full object-cover bg-[var(--bg-hover)]"
                referrerPolicy="no-referrer"
                onError={e => (e.currentTarget.style.display = 'none')}
              />
            )
          ) : (
            /* Нет медиа — placeholder */
            <div className="absolute inset-0 bg-[var(--bg-hover)]/60 flex items-center justify-center text-[var(--text-muted)]">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/>
              </svg>
            </div>
          )}
        </div>

        {/* ── Колонка 2: текст ── */}
        <div className="flex-1 min-w-0 px-4 py-3 flex flex-col justify-center">
          {content ? (
            <div className="text-sm text-[var(--text-secondary)] leading-relaxed">
              <p>{isLong && !expanded ? content.slice(0, 220) + '…' : content}</p>
              {isLong && (
                <button onClick={() => setExpanded(!expanded)}
                  className="text-[var(--accent)] hover:underline text-xs mt-1.5">
                  {expanded ? '↑ Свернуть' : '↓ Читать далее'}
                </button>
              )}
            </div>
          ) : (
            <span className="text-xs text-[var(--text-muted)] italic">Без текста</span>
          )}
        </div>

        {/* ── Колонка 3: статистика + AI + кнопки ── */}
        <div className="w-48 flex-shrink-0 px-3 py-3 flex flex-col gap-2.5">

          {/* Статистика — всегда все 4 строки */}
          <div>
            <p className="text-[9px] font-bold text-[var(--text-muted)] uppercase tracking-widest mb-1.5">Статистика</p>
            <div className="space-y-1.5">
              {([
                { Icon: Eye,           label: 'Просмотры', val: m.views ?? m.plays },
                { Icon: Heart,         label: 'Лайки',     val: m.likes },
                { Icon: MessageCircle, label: 'Комменты',  val: m.comments },
                { Icon: Share2,        label: 'Репосты',   val: m.forwards },
              ] as const).map(({ Icon, label, val }) => (
                <div key={label} className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <Icon size={11} className="text-[var(--text-muted)] flex-shrink-0" />
                    <span className="text-xs text-[var(--text-secondary)] truncate">{label}</span>
                  </div>
                  <span className={`text-sm font-bold tabular-nums ${val ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
                    {fmtNum(val ?? 0)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* AI анализ */}
          <div className={`rounded-lg border p-2 ${V_BORDER[ai.v as keyof typeof V_BORDER]} ${V_BG[ai.v as keyof typeof V_BG]}`}>
            <div className={`flex items-center gap-1 mb-0.5 ${V_TEXT[ai.v as keyof typeof V_TEXT]}`}>
              {ai.v === 'viral' ? <Zap size={9}/> : ai.v === 'good' ? <TrendingUp size={9}/> : <Minus size={9}/>}
              <span className="text-[8px] font-bold uppercase tracking-widest opacity-80">AI Анализ</span>
            </div>
            <p className={`text-xs font-semibold ${V_TEXT[ai.v as keyof typeof V_TEXT]}`}>{ai.emoji} {ai.label}</p>
            <p className="text-[10px] text-[var(--text-muted)] mt-0.5 leading-snug">{ai.text}</p>
          </div>

          {/* Кнопки */}
          <div className="flex flex-col gap-1">
            {/* Кнопка транскрипции — 3 состояния */}
            {transcript ? (
              <button
                onClick={() => setShowModal(true)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-[var(--accent)] border border-[var(--accent)]/40 bg-[var(--accent)]/10 rounded-lg hover:bg-[var(--accent)]/20 transition-colors w-full"
              >
                <FileText size={10}/> Показать текст
              </button>
            ) : transcribing ? (
              <button disabled className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-[var(--text-muted)] border border-[var(--border)] rounded-lg w-full cursor-not-allowed opacity-70">
                <Loader2 size={10} className="animate-spin"/> Транскрибирую...
              </button>
            ) : (
              <button
                onClick={async () => {
                  setTranscribing(true)
                  setTranscribeError('')
                  try {
                    const res = await transcribePost(post.id)
                    setTranscript(res.transcript)
                    setShowModal(true)
                  } catch (e: any) {
                    setTranscribeError(e?.response?.data?.detail || 'Ошибка транскрипции')
                  } finally {
                    setTranscribing(false)
                  }
                }}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-[var(--text-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors w-full"
              >
                <FileText size={10}/> Транскрибировать
              </button>
            )}
            {transcribeError && <p className="text-[10px] text-red-400 leading-tight">{transcribeError}</p>}
            <button
              onClick={() => {
                const el = document.createElement('div')
                el.className = 'fixed bottom-4 right-4 z-50 px-4 py-2 bg-[var(--bg-card)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] shadow-lg'
                el.textContent = '🚧 В разработке'
                document.body.appendChild(el)
                setTimeout(() => el.remove(), 2000)
              }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-[var(--text-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors w-full"
            >
              <CalendarPlus size={10}/> В план контента
            </button>
          </div>

        </div>
      </div>
    </div>
      {showModal && transcript && (
        <TranscriptModal
          transcript={transcript}
          authorName={post.author_name || source?.source_name || ''}
          postedAt={post.posted_at}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  )
}
