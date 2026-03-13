import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright e2e конфигурация.
 * Запуск: npx playwright test
 * Dev-сервер поднимается автоматически на порту 5173.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    // Эмулируем мобильный браузер (Telegram открывается на телефоне)
    ...devices["Pixel 5"],
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chrome",
      use: { ...devices["Pixel 5"] },
    },
  ],
  // Автоматически запускает Vite dev-сервер перед тестами
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      // Подставляем фиктивный initData для обхода авторизации в тестовом режиме
      VITE_DEV_INIT_DATA: "auth_date=9999999999&user=%7B%22id%22%3A123%2C%22first_name%22%3A%22Test%22%7D&hash=testhash",
    },
  },
});
