import { getToken } from './client'

// Типы сообщений
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// Типы SSE-событий от бэкенда
export type SSEEvent =
  | { type: 'token'; content: string }
  | { type: 'tool_call'; name: string; args: Record<string, unknown> }
  | { type: 'done' }
  | { type: 'error'; content: string }

/**
 * Отправить сообщение в AI-чат и получать SSE-поток токенов.
 * onEvent вызывается для каждого SSE-события (токен, tool_call, done, error).
 */
export async function sendChatMessage(
  message: string,
  history: ChatMessage[],
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = getToken()

  // POST-запрос с SSE-ответом
  const res = await fetch('/api/research/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, history }),
    signal,
  })

  if (!res.ok) {
    throw new Error(`Chat API error: ${res.status}`)
  }

  // Чтение SSE-потока через ReadableStream
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    // Декодируем чанк и добавляем в буфер
    buffer += decoder.decode(value, { stream: true })

    // Парсим SSE-строки из буфера
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const event = JSON.parse(line.slice(6)) as SSEEvent
        onEvent(event)
      } catch {
        // Пропускаем невалидные строки
      }
    }
  }
}
