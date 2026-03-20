import { useSearchParams, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { api, saveToken } from '../../api/client'

export function LoginPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const token = params.get('token')

  useEffect(() => {
    if (!token) return
    setLoading(true)
    api.post('/auth/exchange', null, { params: { token } })
      .then(res => { saveToken(res.data.access_token); navigate('/', { replace: true }) })
      .catch(err => { setError(err.response?.data?.detail || 'Ошибка авторизации'); setLoading(false) })
  }, [token, navigate])

  return (
    <div className="text-center max-w-md">
      <h1 className="text-3xl font-bold mb-4">Research Platform</h1>
      <p className="text-[var(--text-secondary)] mb-6">research.thalors.ai</p>
      {loading && <p className="text-[var(--accent)]">Авторизация...</p>}
      {error && <p className="text-[var(--error)]">{error}</p>}
      {!token && !loading && (
        <div className="bg-[var(--bg-card)] p-6 rounded-xl border border-[var(--border)]">
          <p className="text-[var(--text-secondary)] mb-4">Для входа запросите ссылку в Telegram-боте</p>
          <p className="text-sm text-[var(--text-muted)]">Отправьте команду <code className="text-[var(--accent)]">/web</code> боту Jarvis</p>
        </div>
      )}
    </div>
  )
}
