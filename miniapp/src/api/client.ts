/**
 * Axios-клиент с dual-auth:
 * 1. Telegram WebApp initData (приоритет) — заголовок X-Init-Data
 * 2. JWT Bearer token (браузерный fallback) — заголовок Authorization
 *
 * JWT хранится в localStorage после обмена magic-link токена.
 */
import axios from 'axios'

// Ключ для хранения JWT в localStorage
const JWT_STORAGE_KEY = 'jarvis_session_jwt'

// Базовый URL: в продакшне — относительный (nginx proxy), в dev — прямо на порт 8000
const BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

/** Сохранить JWT в localStorage */
export function saveSessionToken(token: string) {
  localStorage.setItem(JWT_STORAGE_KEY, token)
}

/** Получить JWT из localStorage */
export function getSessionToken(): string | null {
  return localStorage.getItem(JWT_STORAGE_KEY)
}

/** Удалить JWT (logout) */
export function clearSessionToken() {
  localStorage.removeItem(JWT_STORAGE_KEY)
}

// Интерцептор запросов: добавляем авторизацию
apiClient.interceptors.request.use((config) => {
  // Приоритет 1: Telegram initData (доступна только внутри Telegram WebApp)
  const initData =
    window.Telegram?.WebApp?.initData ||
    import.meta.env.VITE_DEV_INIT_DATA ||
    ''
  if (initData) {
    config.headers['X-Init-Data'] = initData
    return config
  }

  // Приоритет 2: JWT из localStorage (браузерный доступ через magic link)
  const jwt = getSessionToken()
  if (jwt) {
    config.headers['Authorization'] = `Bearer ${jwt}`
  }

  return config
})

// Интерцептор ответов: обработка ошибок авторизации
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Если нет ни initData, ни валидного JWT — очищаем и редиректим
      const initData = window.Telegram?.WebApp?.initData
      if (!initData) {
        clearSessionToken()
        // Редирект на страницу «нужна авторизация» (если ещё не там)
        if (!window.location.pathname.startsWith('/auth')) {
          window.location.href = '/auth-required'
        }
      }
    }
    return Promise.reject(error)
  }
)
