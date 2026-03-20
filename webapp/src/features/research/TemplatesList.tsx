import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { Plus, Trash2, Play } from 'lucide-react'

const fetchTemplates = () => api.get('/research/templates').then(r => r.data)
const createTemplate = (data: any) => api.post('/research/templates', data).then(r => r.data)
const deleteTemplate = (id: string) => api.delete(`/research/templates/${id}`).then(r => r.data)
const useTemplate = (id: string) => api.post(`/research/templates/${id}/use`).then(r => r.data)

export function TemplatesList() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: templates } = useQuery({ queryKey: ['templates'], queryFn: fetchTemplates })
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')

  const createMut = useMutation({
    mutationFn: () => createTemplate({ name, description: desc }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['templates'] }); setShowForm(false); setName(''); setDesc('') }
  })
  const deleteMut = useMutation({ mutationFn: deleteTemplate, onSuccess: () => qc.invalidateQueries({ queryKey: ['templates'] }) })
  const useMut = useMutation({ mutationFn: useTemplate, onSuccess: (job) => navigate(`/research/jobs/${job.id}`) })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Шаблоны задач</h1>
        <button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2 px-4 py-2 bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white rounded-lg text-sm font-medium">
          <Plus size={16} /> Новый шаблон
        </button>
      </div>

      {showForm && (
        <div className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)] space-y-3">
          <input value={name} onChange={e => setName(e.target.value)} placeholder="Название шаблона"
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm" />
          <textarea value={desc} onChange={e => setDesc(e.target.value)} placeholder="Описание" rows={2}
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg text-sm resize-none" />
          <button onClick={() => createMut.mutate()} disabled={!name} className="px-4 py-2 bg-[var(--accent)] text-white rounded-lg text-sm disabled:opacity-50">Создать</button>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        {templates?.map((t: any) => (
          <div key={t.id} className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)]">
            <div className="flex items-start justify-between">
              <div>
                <div className="font-bold">{t.name}</div>
                {t.description && <p className="text-sm text-[var(--text-muted)] mt-1">{t.description}</p>}
                {t.is_public && <span className="text-xs text-[var(--accent)]">Публичный</span>}
              </div>
              <div className="flex gap-1">
                <button onClick={() => useMut.mutate(t.id)} className="p-1.5 hover:bg-[var(--bg-hover)] rounded" title="Создать задачу"><Play size={14} className="text-green-400" /></button>
                <button onClick={() => deleteMut.mutate(t.id)} className="p-1.5 hover:bg-[var(--bg-hover)] rounded" title="Удалить"><Trash2 size={14} className="text-[var(--error)]" /></button>
              </div>
            </div>
          </div>
        )) || <p className="text-[var(--text-muted)] col-span-2 text-center py-8">Нет шаблонов. Создайте первый!</p>}
      </div>
    </div>
  )
}
