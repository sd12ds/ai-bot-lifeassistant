/**
 * Страница обмена magic-link токена на сессионный JWT.
 * URL: /auth?token=<magic_jwt>
 * Логика: вызывает POST /auth/exchange, сохраняет session JWT, редиректит на /.
 */
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiClient, saveSessionToken } from '../../api/client'

export function AuthGatePage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = searchParams.get('token')
    if (!token) {
      setError('Отсутствует токен авторизации.')
      setLoading(false)
      return
    }

    // Обмениваем magic-токен на сессионный
    apiClient
      .post('/auth/exchange', null, { params: { token } })
      .then((res) => {
        // Сохраняем JWT в localStorage
        saveSessionToken(res.data.access_token)
        // Редирект на главную
        navigate('/', { replace: true })
      })
      .catch((err) => {
        const detail = err.response?.data?.detail || 'Ошибка авторизации'
        setError(`❌ ${detail}. Запросите новую ссылку командой /web в боте.`)
        setLoading(false)
      })
  }, [searchParams, navigate])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '100vh', padding: '2rem',
      textAlign: 'center', color: 'var(--tg-theme-text-color, #fff)',
    }}>
      {loading && !error ? (
        <>
          <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>🔐</div>
          <p>Авторизация...</p>
        </>
      ) : (
        <>
          <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>⚠️</div>
          <p>{error}</p>
        </>
      )}
    </div>
  )
}
