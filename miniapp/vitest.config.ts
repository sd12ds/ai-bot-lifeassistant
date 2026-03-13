/**
 * Конфигурация Vitest для unit-тестов Mini App.
 * Окружение jsdom имитирует браузерный DOM.
 */
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    // Браузерная среда (DOM API)
    environment: 'jsdom',
    // Файл инициализации перед каждым тестом
    setupFiles: ['./src/__tests__/setup.ts'],
    // Glob-паттерны для поиска тестов
    include: ['src/__tests__/**/*.test.{ts,tsx}'],
    // Репортёры: verbose в CI, default локально
    reporters: process.env.CI ? ['verbose'] : ['default'],
    // Покрытие
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/__tests__/**', 'src/main.tsx'],
      thresholds: {
        lines:      70,
        functions:  70,
        branches:   60,
        statements: 70,
      },
    },
    // Глобальные expect/vi/describe без импортов
    globals: true,
  },
  resolve: {
    alias: { '@': '/src' },
  },
})
