/**
 * Хук для работы с Telegram Web App SDK.
 * Предоставляет: initData, данные пользователя, haptic feedback, управление кнопками.
 */
import { useEffect } from 'react'

// Объявляем глобальный тип для Telegram WebApp
declare global {
  interface Window {
    Telegram?: {
      WebApp: {
        ready: () => void
        expand: () => void
        close: () => void
        showConfirm: (message: string, callback: (confirmed: boolean) => void) => void
        showAlert: (message: string, callback?: () => void) => void
        initData: string
        initDataUnsafe: {
          user?: {
            id: number
            first_name: string
            last_name?: string
            username?: string
            photo_url?: string
          }
          hash?: string
        }
        themeParams: Record<string, string>
        colorScheme: 'light' | 'dark'
        BackButton: {
          show: () => void
          hide: () => void
          onClick: (fn: () => void) => void
          offClick: (fn: () => void) => void
        }
        HapticFeedback: {
          impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void
          notificationOccurred: (type: 'error' | 'success' | 'warning') => void
          selectionChanged: () => void
        }
      }
    }
  }
}

// Безопасный геттер WebApp объекта
const getWebApp = () => window.Telegram?.WebApp

export function useTelegram() {
  const webApp = getWebApp()

  useEffect(() => {
    // Сообщаем Telegram, что приложение готово к показу
    webApp?.ready()
    webApp?.expand()
  }, [])

  return {
    webApp,
    // Данные пользователя из initDataUnsafe
    user: webApp?.initDataUnsafe?.user,
    // initData для авторизации (строка для X-Init-Data заголовка)
    initData: webApp?.initData ?? (import.meta.env.VITE_DEV_INIT_DATA ?? ''),
    // Цветовая схема Telegram
    colorScheme: webApp?.colorScheme ?? 'dark',
    // Haptic feedback
    haptic: webApp?.HapticFeedback,
  }
}
