/**
 * Хук применяет Telegram CSS-переменные к документу при монтировании.
 * Это нужно, чтобы наши --app-* переменные корректно получили значения из Telegram.
 */
import { useEffect } from 'react'

export function useTheme() {
  useEffect(() => {
    const tg = window.Telegram?.WebApp
    if (!tg) return

    const params = tg.themeParams
    const root = document.documentElement

    // Маппинг: ключ из Telegram → CSS-переменная
    const mapping: Record<string, string> = {
      bg_color:           '--tg-theme-bg-color',
      section_bg_color:   '--tg-theme-section-bg-color',
      text_color:         '--tg-theme-text-color',
      hint_color:         '--tg-theme-hint-color',
      link_color:         '--tg-theme-link-color',
      button_color:       '--tg-theme-button-color',
      button_text_color:  '--tg-theme-button-text-color',
      secondary_bg_color: '--tg-theme-secondary-bg-color',
    }

    // Применяем переменные к :root
    Object.entries(mapping).forEach(([key, cssVar]) => {
      if (params[key]) {
        root.style.setProperty(cssVar, params[key])
      }
    })

    // Применяем colorScheme к <html> для ориентирования CSS
    root.setAttribute('data-theme', tg.colorScheme ?? 'dark')
  }, [])
}
