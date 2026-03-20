import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { createJob, runJob } from '../../api/research'
import { useNavigate } from 'react-router-dom'

export function NewJobForm() {
  const navigate = useNavigate()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [jobType, setJobType] = useState('search')
  const [urls, setUrls] = useState('')
  const [fields, setFields] = useState('')

  const mutation = useMutation({
    mutationFn: async () => {
      const spec: any = { objective: description }
      if (urls) spec.urls = urls.split('\n').map((u: string) => u.trim()).filter(Boolean)
      if (fields) spec.extraction_schema = Object.fromEntries(fields.split(',').map(f => [f.trim(), 'string']))
      const job = await createJob({ title, description, job_type: jobType, normalized_spec: spec, original_request: description })
      await runJob(job.id)
      return job
    },
    onSuccess: (job) => navigate(`/research/jobs/${job.id}`),
  })

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Новая задача сбора</h1>
      <div className="bg-[var(--bg-card)] rounded-xl p-6 border border-[var(--border)] space-y-4">
        <div>
          <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">Название</label>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Конкуренты в нише AI ассистентов"
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:border-[var(--accent)]" />
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">Описание задачи</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)} rows={3} placeholder="Найти компании-конкурентов, собрать сайт, контакты, описание продуктов"
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:border-[var(--accent)] resize-none" />
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">Тип задачи</label>
          <select value={jobType} onChange={e => setJobType(e.target.value)}
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:border-[var(--accent)]">
            <option value="search">Поиск (search)</option>
            <option value="crawl">Обход сайта (crawl)</option>
            <option value="scrape">Скрейпинг (scrape)</option>
            <option value="extract">Извлечение данных (extract)</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">URL-адреса (по одному на строку)</label>
          <textarea value={urls} onChange={e => setUrls(e.target.value)} rows={2} placeholder="https://example.com"
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:border-[var(--accent)] resize-none" />
        </div>
        <div>
          <label className="block text-sm font-medium text-[var(--text-muted)] mb-1">Поля для извлечения (через запятую)</label>
          <input value={fields} onChange={e => setFields(e.target.value)} placeholder="название, сайт, телефон, email, описание"
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:border-[var(--accent)]" />
        </div>
        <button onClick={() => mutation.mutate()} disabled={!title || mutation.isPending}
          className="w-full py-2.5 bg-[var(--accent)] hover:bg-[var(--accent-hover)] disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
          {mutation.isPending ? 'Создание...' : 'Создать и запустить'}
        </button>
        {mutation.error && <p className="text-sm text-[var(--error)]">Ошибка: {String(mutation.error)}</p>}
      </div>
    </div>
  )
}
