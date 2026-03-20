import axios from 'axios'

const JWT_KEY = 'research_session_jwt'
const BASE_URL = '/api'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true, // отправлять cookies для httpOnly
})

// localStorage fallback для magic link flow
export function saveToken(token: string) { localStorage.setItem(JWT_KEY, token) }
export function getToken(): string | null { return localStorage.getItem(JWT_KEY) }
export function clearToken() { localStorage.removeItem(JWT_KEY) }

// Интерцептор: JWT из localStorage (fallback) или cookie (primary)
api.interceptors.request.use((config) => {
  const jwt = getToken()
  if (jwt) config.headers['Authorization'] = `Bearer ${jwt}`
  return config
})

// Интерцептор: 401 → попытка refresh → redirect на login
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401 && !err.config._retry) {
      err.config._retry = true
      try {
        // Попытка обновить через refresh cookie
        await axios.post('/api/auth/refresh', null, { withCredentials: true })
        return api(err.config) // повтор запроса
      } catch {
        clearToken()
        if (!window.location.pathname.startsWith('/auth'))
          window.location.href = '/auth'
      }
    }
    return Promise.reject(err)
  }
)
