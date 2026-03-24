/**
 * Хук фиксирует тёмную тему при монтировании.
 * ринудительно задаёт data-theme='dark' и тёмный цвет заголовка/фона в Telegram,
 * чтобы miniapp не менял оформление при переключении темы в Telegram.
 */
import { useEffect } from 'react'

export function useTheme() {
  useEffect(() => {
    const tg = window.Telegram?.WebApp

    // сегда принудительно ставим тёмную тему, независимо от Telegram
    document.documentElement.setAttribute('data-theme', 'dark')

    if (!tg) return

    // ринудительно задаём тёмный цвет заголовка и фона Telegram WebApp
    try {
      tg.setHeaderColor?.('#0f0f1a')
      tg.setBackgroundColor?.('#0f0f1a')
    } catch {
      // е все версии Telegram поддерживают эти методы — игнорируем
    }
  }, [])
}
