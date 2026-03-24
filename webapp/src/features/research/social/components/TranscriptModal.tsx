/**
 * TranscriptModal — модальное окно с транскриптом рила.
 * Открывается кнопкой "Показать текст" в PostCard.
 */
import { useState } from 'react'
import { X, Copy, Check, FileText } from 'lucide-react'

interface Props {
  transcript: string
  authorName: string
  postedAt: string | null
  onClose: () => void
}

function fmtDate(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
}

export function TranscriptModal({ transcript, authorName, postedAt, onClose }: Props) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(transcript)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}>
        {/* Модальное окно */}
        <div
          className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl w-full max-w-lg shadow-2xl"
          onClick={e => e.stopPropagation()}
        >
          {/* Шапка */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
            <div className="flex items-center gap-2">
              <FileText size={16} className="text-[var(--accent)]" />
              <span className="font-semibold text-[var(--text-primary)]">Транскрипция</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-[var(--text-muted)]">
                @{authorName}{postedAt ? ` · ${fmtDate(postedAt)}` : ''}
              </span>
              <button onClick={onClose} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors">
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Текст */}
          <div className="px-5 py-4 max-h-80 overflow-y-auto">
            <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
              {transcript}
            </p>
          </div>

          {/* Футер */}
          <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--border)]">
            <span className="text-xs text-[var(--text-muted)]">
              {transcript.split(/\s+/).length} слов · {transcript.length} символов
            </span>
            <div className="flex gap-2">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--accent)]/15 text-[var(--accent)] border border-[var(--accent)]/30 rounded-lg hover:bg-[var(--accent)]/25 transition-colors"
              >
                {copied ? <><Check size={12} /> Скопировано!</> : <><Copy size={12} /> Копировать</>}
              </button>
              <button onClick={onClose}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-secondary)] border border-[var(--border)] rounded-lg hover:bg-[var(--bg-hover)] transition-colors">
                <X size={12} /> Закрыть
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
