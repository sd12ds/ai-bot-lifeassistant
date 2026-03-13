/**
 * Глобальная инициализация тестового окружения.
 * Запускается перед каждым тестовым файлом.
 */
import '@testing-library/jest-dom'
import { afterEach, beforeAll, afterAll, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
import { server } from './mocks/server'

// Запускаем MSW-сервер перед всеми тестами
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))

// Сбрасываем обработчики после каждого теста
afterEach(() => {
  server.resetHandlers()
  cleanup() // размонтируем React-дерево
})

// Останавливаем сервер после всех тестов
afterAll(() => server.close())

// Мок для matchMedia (jsdom не поддерживает)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Мок window.Telegram для всех тестов
window.Telegram = {
  WebApp: {
    ready: vi.fn(),
    expand: vi.fn(),
    close: vi.fn(),
    initData: 'mock_init_data',
    initDataUnsafe: {
      user: { id: 123456, first_name: 'Тест', username: 'testuser' },
    },
    themeParams: {},
    colorScheme: 'dark',
    BackButton: {
      show: vi.fn(), hide: vi.fn(),
      onClick: vi.fn(), offClick: vi.fn(),
    },
    HapticFeedback: {
      impactOccurred: vi.fn(),
      notificationOccurred: vi.fn(),
      selectionChanged: vi.fn(),
    },
  },
}
