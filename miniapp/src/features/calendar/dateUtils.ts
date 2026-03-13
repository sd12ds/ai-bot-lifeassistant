/**
 * Утилиты для работы с датами в локальном часовом поясе.
 * toISOString() конвертирует в UTC — это ломает группировку по дням
 * для пользователей не в UTC (например, МСК = UTC+3).
 */

/** Форматирует Date в строку YYYY-MM-DD в локальном часовом поясе */
export function toLocalDateStr(d: Date): string {
  // Используем getFullYear/getMonth/getDate — они в локальном TZ
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** Парсит ISO-строку из API и возвращает локальную дату YYYY-MM-DD */
export function isoToLocalDateStr(iso: string): string {
  return toLocalDateStr(new Date(iso))
}
