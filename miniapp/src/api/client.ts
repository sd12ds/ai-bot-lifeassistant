/**
 * Axios-клиент с интерцептором для Telegram initData авторизации.
 * Каждый запрос автоматически получает заголовок X-Init-Data.
 */
import axios from 'axios'

// Базовый URL: в продакшне — относительный (nginx proxy), в dev — прямо на порт 8000
const BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

// Интерцептор запросов: добавляем Telegram initData в заголовок
apiClient.interceptors.request.use((config) => {
  // Получаем initData из Telegram SDK или из env для дев-среды
  const initData =
    window.Telegram?.WebApp?.initData ||
    import.meta.env.VITE_DEV_INIT_DATA ||
    ''
  if (initData) {
    config.headers['X-Init-Data'] = initData
  }
  return config
})

// Интерцептор ответов: единый обработчик ошибок
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 — initData невалидна или истекла
    if (error.response?.status === 401) {
      console.error('Auth error: invalid or expired initData')
    }
    return Promise.reject(error)
  }
)
