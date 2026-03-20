import axios from 'axios'

const JWT_KEY = 'research_session_jwt'
const BASE_URL = '/api'

export const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

export function saveToken(token: string) { localStorage.setItem(JWT_KEY, token) }
export function getToken(): string | null { return localStorage.getItem(JWT_KEY) }
export function clearToken() { localStorage.removeItem(JWT_KEY) }

// Интерцептор: добавляем JWT в каждый запрос
api.interceptors.request.use((config) => {
  const jwt = getToken()
  if (jwt) config.headers['Authorization'] = `Bearer ${jwt}`
  return config
})

// Интерцептор: обработка 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearToken()
      if (!window.location.pathname.startsWith('/auth'))
        window.location.href = '/auth'
    }
    return Promise.reject(err)
  }
)
