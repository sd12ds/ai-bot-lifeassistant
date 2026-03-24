import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Loader2, Bot, User, Wrench, Trash2 } from 'lucide-react'
import { sendChatMessage, type ChatMessage, type SSEEvent } from '../../api/chat'

// Сообщение в UI (расширенный тип с meta-данными)
interface UIMessage {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: { name: string; args: Record<string, unknown> }[]
}

// Маппинг имён tool → читаемый текст
const TOOL_LABELS: Record<string, string> = {
  list_jobs: 'Загрузка задач…',
  get_job_details: 'Получение деталей задачи…',
  create_job: 'Создание задачи…',
  run_job: 'Запуск задачи…',
  cancel_job: 'Отмена задачи…',
  get_stats: 'Загрузка статистики…',
  get_results: 'Загрузка результатов…',
}

export function ChatPage() {
  // Состояние чата
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentToolCall, setCurrentToolCall] = useState<string | null>(null)

  // Реф для автоскролла
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Автоскролл к последнему сообщению
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentToolCall, scrollToBottom])

  // Автофокус на input
  useEffect(() => {
    inputRef.current?.focus()
  }, [isStreaming])

  // Отправка сообщения
  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || isStreaming) return

    // Добавляем сообщение пользователя
    const userMsg: UIMessage = { role: 'user', content: text }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsStreaming(true)
    setCurrentToolCall(null)

    // Собираем историю для API (без toolCalls)
    const history: ChatMessage[] = messages.map(m => ({
      role: m.role,
      content: m.content,
    }))

    // Аккумулятор текста ассистента
    let assistantContent = ''
    const toolCalls: { name: string; args: Record<string, unknown> }[] = []

    // Добавляем пустое сообщение ассистента для стриминга
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    // Создаём AbortController для отмены запроса
    const abort = new AbortController()
    abortRef.current = abort

    try {
      await sendChatMessage(
        text,
        history,
        (event: SSEEvent) => {
          switch (event.type) {
            case 'token':
              // Добавляем токен к последнему сообщению ассистента
              assistantContent += event.content
              setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: assistantContent,
                  toolCalls: toolCalls.length > 0 ? [...toolCalls] : undefined,
                }
                return updated
              })
              break

            case 'tool_call':
              // Показываем индикатор вызова функции
              toolCalls.push({ name: event.name, args: event.args })
              setCurrentToolCall(TOOL_LABELS[event.name] || `Выполнение: ${event.name}…`)
              break

            case 'done':
              // Стриминг завершён
              setCurrentToolCall(null)
              break

            case 'error':
              // Ошибка — добавляем в сообщение
              setMessages(prev => {
                const updated = [...prev]
                updated[updated.length - 1] = {
                  role: 'assistant',
                  content: `⚠️ Ошибка: ${event.content}`,
                }
                return updated
              })
              break
          }
        },
        abort.signal,
      )
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        // Добавляем сообщение об ошибке
        setMessages(prev => {
          const updated = [...prev]
          if (updated.length > 0 && updated[updated.length - 1].role === 'assistant') {
            updated[updated.length - 1] = {
              role: 'assistant',
              content: `⚠️ Ошибка соединения: ${(err as Error).message}`,
            }
          }
          return updated
        })
      }
    } finally {
      setIsStreaming(false)
      setCurrentToolCall(null)
      abortRef.current = null
    }
  }, [input, isStreaming, messages])

  // Обработка Enter (Shift+Enter — новая строка)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Очистка чата
  const handleClear = () => {
    if (isStreaming) {
      abortRef.current?.abort()
    }
    setMessages([])
    setInput('')
    setIsStreaming(false)
    setCurrentToolCall(null)
  }

  return (
    <div className="flex flex-col h-full max-h-[calc(100vh-5rem)]">
      {/* Заголовок */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Чат</h1>
        {messages.length > 0 && (
          <button
            onClick={handleClear}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--error)] transition-colors rounded-lg hover:bg-[var(--bg-hover)]"
          >
            <Trash2 size={16} />
            Очистить
          </button>
        )}
      </div>

      {/* Область сообщений */}
      <div className="flex-1 overflow-auto rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] p-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-[var(--text-muted)] gap-3">
            <Bot size={48} strokeWidth={1.5} />
            <p className="text-lg">AI-ассистент Research Platform</p>
            <p className="text-sm text-center max-w-md">
              Спросите о задачах, статистике или попросите создать новое исследование.
              Например: «Покажи мои задачи» или «Создай задачу: анализ рынка AI»
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {/* Аватар ассистента */}
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-full bg-[var(--accent)]/20 flex items-center justify-center shrink-0 mt-1">
                <Bot size={16} className="text-[var(--accent)]" />
              </div>
            )}

            {/* Содержимое сообщения */}
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                msg.role === 'user'
                  ? 'bg-[var(--accent)] text-white rounded-br-md'
                  : 'bg-[var(--bg-card)] text-[var(--text-primary)] rounded-bl-md'
              }`}
            >
              {msg.content || (isStreaming && i === messages.length - 1 ? '' : '...')}
            </div>

            {/* Аватар пользователя */}
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-[var(--bg-hover)] flex items-center justify-center shrink-0 mt-1">
                <User size={16} className="text-[var(--text-secondary)]" />
              </div>
            )}
          </div>
        ))}

        {/* Индикатор вызова функции */}
        {currentToolCall && (
          <div className="flex items-center gap-2 text-sm text-[var(--text-muted)] pl-11">
            <Wrench size={14} className="animate-spin" />
            {currentToolCall}
          </div>
        )}

        {/* Индикатор «печатает...» */}
        {isStreaming && !currentToolCall && messages.length > 0 && messages[messages.length - 1].content === '' && (
          <div className="flex items-center gap-2 text-sm text-[var(--text-muted)] pl-11">
            <Loader2 size={14} className="animate-spin" />
            Думаю...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Поле ввода */}
      <div className="mt-3 flex gap-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Напишите сообщение..."
          rows={1}
          disabled={isStreaming}
          className="flex-1 resize-none rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] px-4 py-3 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 focus:border-[var(--accent)] disabled:opacity-50 transition-colors"
          style={{ minHeight: '48px', maxHeight: '120px' }}
          onInput={e => {
            // Авто-resize textarea
            const el = e.currentTarget
            el.style.height = 'auto'
            el.style.height = Math.min(el.scrollHeight, 120) + 'px'
          }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isStreaming}
          className="px-4 rounded-xl bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
        >
          {isStreaming ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </div>
    </div>
  )
}
