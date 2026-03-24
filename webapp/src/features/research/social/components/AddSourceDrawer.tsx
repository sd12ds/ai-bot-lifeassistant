/** AddSourceDrawer — 3-шаговый визард добавления источника (slide-in панель). */
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X, ArrowRight, ArrowLeft, Check, Search, Loader2 } from 'lucide-react'
import { createSource, resolveSourceUrl } from '../../../../api/social'
import { PlatformBadge } from './PlatformBadge'
import { CollectionConfigPanel } from './CollectionConfigPanel'
import { SchedulePicker } from './SchedulePicker'

interface Props {
  open: boolean
  onClose: () => void
}

interface ResolvedInfo {
  platform: string
  source_id: string
  source_name: string
  source_type: string
  subscribers_count: number
  photo_url: string
}

const STEP_LABELS = ['URL', 'Настройки', 'Расписание']

export function AddSourceDrawer({ open, onClose }: Props) {
  const qc = useQueryClient()
  const [step, setStep] = useState(0)
  const [url, setUrl]   = useState('')
  const [resolved, setResolved] = useState<ResolvedInfo | null>(null)
  const [resolveError, setResolveError] = useState('')
  const [resultsType, setResultsType]     = useState('posts')
  const [extras, setExtras] = useState({ metrics: true, media: true, hashtags: false, mentions: false })
  const [limit, setLimit]   = useState(50)
  const [intervalHours, setIntervalHours] = useState(6)
  const [runNow, setRunNow] = useState(true)

  const resolving = useMutation({
    mutationFn: () => resolveSourceUrl(url),
    onSuccess: (data: any) => {
      setResolved(data)
      setResolveError('')
      // Авто-определяем resultsType по платформе/URL
      if (url.includes('/explore/tags/')) setResultsType('hashtag')
      else if (url.includes('/explore/locations/')) setResultsType('location')
      else if (url.includes('/p/')) setResultsType('comments')
      else setResultsType('posts')
    },
    onError: (e: any) => setResolveError(e?.response?.data?.detail || 'Не удалось определить источник'),
  })

  const submit = useMutation({
    mutationFn: () => createSource({
      url,
      collection_config: {
        results_type: resultsType,
        ...extras,
        limit,
      },
      schedule: { interval_hours: intervalHours },
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['social-sources'] })
      qc.invalidateQueries({ queryKey: ['social-stats'] })
      handleClose()
    },
  })

  const handleClose = () => {
    setStep(0); setUrl(''); setResolved(null); setResolveError('')
    setResultsType('posts'); setLimit(50); setIntervalHours(6); setRunNow(true)
    onClose()
  }

  if (!open) return null

  return (
    <>
      {/* Overlay */}
      <div className="fixed inset-0 bg-black/50 z-40" onClick={handleClose} />

      {/* Панель */}
      <div className="fixed right-0 top-0 h-full w-[420px] bg-[var(--bg-secondary)] border-l border-[var(--border)] z-50 flex flex-col shadow-2xl">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-5 border-b border-[var(--border)]">
          <h2 className="font-semibold text-[var(--text-primary)]">Добавить источник</h2>
          <button onClick={handleClose} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <X size={18} />
          </button>
        </div>

        {/* Step indicator */}
        <div className="flex gap-0 px-5 pt-4">
          {STEP_LABELS.map((label, i) => (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors
                ${i < step ? 'bg-[var(--accent)] text-white' : i === step ? 'bg-[var(--accent)]/20 text-[var(--accent)] border border-[var(--accent)]' : 'bg-[var(--bg-hover)] text-[var(--text-muted)]'}`}>
                {i < step ? <Check size={12} /> : i + 1}
              </div>
              <span className={`text-xs ${i === step ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>{label}</span>
              {i < STEP_LABELS.length - 1 && <div className="flex-1 h-px bg-[var(--border)] ml-2" />}
            </div>
          ))}
        </div>

        {/* Контент шага */}
        <div className="flex-1 overflow-y-auto p-5">
          {/* Шаг 1 — URL */}
          {step === 0 && (
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-[var(--text-secondary)] block mb-2">
                  Ссылка или username
                </label>
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                  <input
                    type="text"
                    value={url}
                    onChange={e => { setUrl(e.target.value); setResolved(null); setResolveError('') }}
                    onKeyDown={e => e.key === 'Enter' && url && resolving.mutate()}
                    placeholder="t.me/channel или instagram.com/profile"
                    className="w-full pl-9 pr-4 py-2.5 bg-[var(--bg-hover)] border border-[var(--border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
                {resolveError && <p className="text-xs text-red-400 mt-1">{resolveError}</p>}
              </div>

              {/* Preview */}
              {resolving.isPending && (
                <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                  <Loader2 size={14} className="animate-spin" />Определяем источник...
                </div>
              )}
              {resolved && (
                <div className="flex items-center gap-3 p-3 bg-[var(--bg-hover)] rounded-xl border border-[var(--border)]">
                  {resolved.photo_url && (
                    <img src={resolved.photo_url} alt="" className="w-10 h-10 rounded-full object-cover" onError={e => e.currentTarget.style.display = 'none'} />
                  )}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate">{resolved.source_name}</span>
                      <PlatformBadge platform={resolved.platform} showLabel size="sm" />
                    </div>
                    {resolved.subscribers_count > 0 && (
                      <p className="text-xs text-[var(--text-muted)]">
                        {resolved.subscribers_count >= 1000
                          ? `${(resolved.subscribers_count / 1000).toFixed(1)}K`
                          : resolved.subscribers_count} подписчиков
                      </p>
                    )}
                  </div>
                  <Check size={16} className="text-green-400 flex-shrink-0" />
                </div>
              )}

              {!resolved && !resolving.isPending && url && (
                <button
                  onClick={() => resolving.mutate()}
                  className="w-full py-2 text-sm bg-[var(--accent)]/20 text-[var(--accent)] rounded-lg hover:bg-[var(--accent)]/30 transition-colors"
                >
                  Определить источник
                </button>
              )}
            </div>
          )}

          {/* Шаг 2 — Настройки */}
          {step === 1 && resolved && (
            <CollectionConfigPanel
              platform={resolved.platform}
              resultsType={resultsType}
              onResultsTypeChange={setResultsType}
              extras={extras}
              onExtrasChange={(k, v) => setExtras(prev => ({ ...prev, [k]: v }))}
              limit={limit}
              onLimitChange={setLimit}
            />
          )}

          {/* Шаг 3 — Расписание */}
          {step === 2 && (
            <div className="space-y-5">
              <div>
                <p className="text-sm font-medium text-[var(--text-secondary)] mb-3">Как часто собирать</p>
                <SchedulePicker value={intervalHours} onChange={setIntervalHours} />
              </div>
              <div className="space-y-2">
                <p className="text-sm font-medium text-[var(--text-secondary)] mb-2">Первый запуск</p>
                {[
                  { val: true,  label: 'Сразу после добавления' },
                  { val: false, label: 'По расписанию' },
                ].map(opt => (
                  <label key={String(opt.val)} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="run_now" checked={runNow === opt.val} onChange={() => setRunNow(opt.val)}
                      className="accent-[var(--accent)]" />
                    <span className="text-sm text-[var(--text-primary)]">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-5 border-t border-[var(--border)] flex gap-3">
          {step > 0 && (
            <button onClick={() => setStep(s => s - 1)}
              className="flex items-center gap-1 px-4 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] rounded-lg transition-colors">
              <ArrowLeft size={14} /> Назад
            </button>
          )}
          <div className="flex-1" />
          {step < 2 ? (
            <button
              disabled={step === 0 && !resolved}
              onClick={() => { if (step === 0 && !resolved) resolving.mutate(); else setStep(s => s + 1) }}
              className="flex items-center gap-1 px-5 py-2 text-sm bg-[var(--accent)] text-white rounded-lg hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-40"
            >
              Продолжить <ArrowRight size={14} />
            </button>
          ) : (
            <button
              onClick={() => submit.mutate()}
              disabled={submit.isPending}
              className="flex items-center gap-1 px-5 py-2 text-sm bg-[var(--accent)] text-white rounded-lg hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-60"
            >
              {submit.isPending ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
              {submit.isPending ? 'Добавляем...' : 'Добавить источник'}
            </button>
          )}
        </div>
      </div>
    </>
  )
}
