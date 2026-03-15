/**
 * CheckInHelpPage — интерактивная инструкция по чекинам.
 *
 * Структура:
 *  - Три accordion-секции по слотам (Утро / День / Вечер)
 *  - Секция «Как отправить голосовой»
 *  - Секция «Автоопределение слота»
 *  - Примеры фраз для бота
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, ArrowLeft, Mic, Sun, Zap, Moon, Clock, MessageSquare } from 'lucide-react'
import { GlassCard } from '../../shared/ui/GlassCard'

// ── Типы ──────────────────────────────────────────────────────────────────────

interface AccordionItem {
  id: string
  icon: React.ReactNode
  title: string
  subtitle: string
  color: string
  content: React.ReactNode
}

// ── Компонент аккордеона ──────────────────────────────────────────────────────

function Accordion({ items }: { items: AccordionItem[] }) {
  const [openId, setOpenId] = useState<string | null>(null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {items.map(item => {
        const isOpen = openId === item.id
        return (
          <div
            key={item.id}
            style={{
              borderRadius: 14,
              overflow: 'hidden',
              border: `1px solid ${isOpen ? item.color + '55' : 'rgba(255,255,255,0.08)'}`,
              background: isOpen ? 'rgba(255,255,255,0.04)' : 'rgba(255,255,255,0.02)',
              transition: 'border-color 0.2s, background 0.2s',
            }}
          >
            {/* Заголовок аккордеона */}
            <button
              onClick={() => setOpenId(isOpen ? null : item.id)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '14px 16px',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: '#fff',
                textAlign: 'left',
              }}
            >
              <span style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: item.color + '22',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: item.color,
                flexShrink: 0,
              }}>
                {item.icon}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 15, color: '#f1f5f9' }}>{item.title}</div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>{item.subtitle}</div>
              </div>
              <ChevronDown
                size={18}
                style={{
                  color: '#64748b',
                  transform: isOpen ? 'rotate(180deg)' : 'none',
                  transition: 'transform 0.2s',
                  flexShrink: 0,
                }}
              />
            </button>

            {/* Содержимое аккордеона */}
            {isOpen && (
              <div style={{
                padding: '0 16px 16px',
                color: '#cbd5e1',
                fontSize: 14,
                lineHeight: 1.6,
              }}>
                {item.content}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Компонент карточки примера ─────────────────────────────────────────────────

function ExampleCard({ text, label }: { text: string; label: string }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.05)',
      borderRadius: 10,
      padding: '10px 14px',
      marginTop: 8,
      borderLeft: '3px solid rgba(99,102,241,0.6)',
    }}>
      <div style={{ fontSize: 11, color: '#6366f1', marginBottom: 4, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 13, color: '#e2e8f0', fontStyle: 'italic' }}>«{text}»</div>
    </div>
  )
}

// ── Поля по слоту ─────────────────────────────────────────────────────────────

function FieldBadge({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '3px 10px',
      borderRadius: 20,
      fontSize: 12,
      fontWeight: 500,
      background: color + '22',
      color: color,
      marginRight: 6,
      marginBottom: 6,
    }}>
      {label}
    </span>
  )
}

// ── Содержимое слотов ──────────────────────────────────────────────────────────

const morningContent = (
  <div>
    <p style={{ marginTop: 0, marginBottom: 12, color: '#94a3b8' }}>
      Утренний чекин помогает зафиксировать стартовый уровень энергии и настроиться на день.
      Лучшее время — <strong style={{ color: '#fbbf24' }}>6:00–11:00</strong>.
    </p>
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}>Поля:</div>
      <FieldBadge label="⚡ Энергия (1–5)" color="#fbbf24" />
      <FieldBadge label="📝 Заметки" color="#a3a3a3" />
    </div>
    <ExampleCard text="Утром энергия 4, настроен позитивно, хочу сделать сложную задачу" label="Пример голосового" />
    <ExampleCard text="Утренний чекин: энергия 3, немного не выспался, но соберусь" label="Ещё пример" />
  </div>
)

const middayContent = (
  <div>
    <p style={{ marginTop: 0, marginBottom: 12, color: '#94a3b8' }}>
      Дневной пульс — короткий срез в середине дня. Помогает скорректировать вторую половину.
      Лучшее время — <strong style={{ color: '#22d3ee' }}>12:00–16:00</strong>.
    </p>
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}>Поля:</div>
      <FieldBadge label="⚡ Энергия (1–5)" color="#22d3ee" />
      <FieldBadge label="📝 Заметки" color="#a3a3a3" />
    </div>
    <ExampleCard text="Дневной чекин, энергия 2, устал после митингов, нужен перерыв" label="Пример голосового" />
    <ExampleCard text="В обед: энергия 5, всё идёт по плану, сделал половину задач" label="Ещё пример" />
  </div>
)

const eveningContent = (
  <div>
    <p style={{ marginTop: 0, marginBottom: 12, color: '#94a3b8' }}>
      Вечерняя рефлексия — самый важный слот. Бот использует эти данные для персональных советов.
      Лучшее время — <strong style={{ color: '#a78bfa' }}>17:00–23:00</strong>.
    </p>
    <div style={{ marginBottom: 10 }}>
      <div style={{ fontSize: 12, color: '#64748b', marginBottom: 6 }}>Поля:</div>
      <FieldBadge label="💭 Настроение" color="#a78bfa" />
      <FieldBadge label="⚡ Энергия (1–5)" color="#fbbf24" />
      <FieldBadge label="📝 Как прошёл день" color="#a3a3a3" />
      <FieldBadge label="🏆 Победы" color="#4ade80" />
      <FieldBadge label="🚧 Блокеры" color="#f87171" />
    </div>
    <ExampleCard
      text="Вечерний чекин: настроение хорошее, энергия 3. День прошёл продуктивно, закрыл 2 задачи. Победа — наконец выпустил фичу. Мешало — много переключений"
      label="Пример голосового (полный)"
    />
    <ExampleCard text="Итог дня: настроение ок, энергия 2, устал. Хорошо поработал, победы — написал план на неделю" label="Краткий вариант" />
  </div>
)

// ── Основной компонент ─────────────────────────────────────────────────────────

export function CheckInHelpPage() {
  const navigate = useNavigate()

  // Аккордеон слотов
  const slotItems: AccordionItem[] = [
    {
      id: 'morning',
      icon: <Sun size={18} />,
      title: 'Утренний чекин',
      subtitle: '6:00–11:00 · Энергия + заметки',
      color: '#fbbf24',
      content: morningContent,
    },
    {
      id: 'midday',
      icon: <Zap size={18} />,
      title: 'Дневной чекин',
      subtitle: '12:00–16:00 · Дневной пульс',
      color: '#22d3ee',
      content: middayContent,
    },
    {
      id: 'evening',
      icon: <Moon size={18} />,
      title: 'Вечерний чекин',
      subtitle: '17:00–23:00 · Полная рефлексия',
      color: '#a78bfa',
      content: eveningContent,
    },
  ]

  // Аккордеон голосового + автоопределения
  const voiceItems: AccordionItem[] = [
    {
      id: 'voice',
      icon: <Mic size={18} />,
      title: 'Как отправить голосовой',
      subtitle: 'Записи голоса · Шаг за шагом',
      color: '#34d399',
      content: (
        <div>
          <ol style={{ margin: 0, paddingLeft: 20, color: '#94a3b8' }}>
            <li style={{ marginBottom: 8 }}>Открой чат с ботом в Telegram</li>
            <li style={{ marginBottom: 8 }}>Зажми кнопку микрофона и надиктуй чекин</li>
            <li style={{ marginBottom: 8 }}>
              Бот распознает речь, извлечёт поля и покажет карточку подтверждения
            </li>
            <li style={{ marginBottom: 8 }}>
              Нажми <strong style={{ color: '#34d399' }}>✅ Сохранить</strong> — чекин попадёт в историю
            </li>
            <li>
              Или <strong style={{ color: '#fbbf24' }}>✏️ Изменить</strong> — уточни детали голосом или текстом
            </li>
          </ol>
          <div style={{ marginTop: 12, padding: '10px 14px', background: 'rgba(52,211,153,0.08)', borderRadius: 10, border: '1px solid rgba(52,211,153,0.2)' }}>
            <div style={{ fontSize: 12, color: '#34d399', fontWeight: 600, marginBottom: 4 }}>💡 Совет</div>
            <div style={{ fontSize: 13, color: '#94a3b8' }}>
              Текстовые сообщения тоже работают — просто напиши чекин как обычное сообщение боту
            </div>
          </div>
        </div>
      ),
    },
    {
      id: 'slot-detection',
      icon: <Clock size={18} />,
      title: 'Автоопределение слота',
      subtitle: 'Как бот понимает утро/день/вечер',
      color: '#fb923c',
      content: (
        <div>
          <p style={{ marginTop: 0, color: '#94a3b8' }}>
            Бот определяет слот в следующем порядке:
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px' }}>
              <div style={{ fontSize: 12, color: '#fb923c', fontWeight: 600 }}>1. Ключевые слова</div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginTop: 4 }}>
                «утром», «вечером», «в обед», «итог дня» → соответствующий слот
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px' }}>
              <div style={{ fontSize: 12, color: '#fb923c', fontWeight: 600 }}>2. Числовое время</div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginTop: 4 }}>
                «в 8 утра» → утро · «в 13:00» → день · «в 20:00» → вечер
              </div>
            </div>
            <div style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px' }}>
              <div style={{ fontSize: 12, color: '#fb923c', fontWeight: 600 }}>3. Текущее время (если ничего нет)</div>
              <div style={{ fontSize: 13, color: '#cbd5e1', marginTop: 4 }}>
                5–11h → утро · 12–16h → день · 17–23h → вечер
              </div>
            </div>
          </div>
          <p style={{ marginBottom: 0, marginTop: 12, color: '#94a3b8', fontSize: 13 }}>
            Дата определяется так же: «вчера», «3 марта», «в понедельник» — бот поймёт.
            Без указания — сегодня.
          </p>
        </div>
      ),
    },
    {
      id: 'examples',
      icon: <MessageSquare size={18} />,
      title: 'Примеры фраз',
      subtitle: 'Готовые шаблоны для голосового',
      color: '#818cf8',
      content: (
        <div>
          <div style={{ fontSize: 12, color: '#64748b', marginBottom: 8 }}>🌅 Утренние</div>
          <ExampleCard text="Утром энергия 5, отлично выспался, готов к работе" label="Короткий" />
          <ExampleCard text="Утренний чекин: энергия 3, немного устал, но настроен. Сегодня хочу закрыть проект" label="С планом" />

          <div style={{ fontSize: 12, color: '#64748b', marginTop: 14, marginBottom: 8 }}>☀️ Дневные</div>
          <ExampleCard text="Дневной пульс: энергия 4, работа идёт хорошо" label="Краткий" />
          <ExampleCard text="В обед энергия упала до 2, много митингов. Пойду на прогулку" label="С заметкой" />

          <div style={{ fontSize: 12, color: '#64748b', marginTop: 14, marginBottom: 8 }}>🌙 Вечерние</div>
          <ExampleCard text="Итог дня: настроение хорошее, энергия 3. Закрыл дизайн, это победа. Мешала прокрастинация" label="Стандартный" />
          <ExampleCard text="Вечер, настроение отличное, энергия 4. День был продуктивным. Победы: выпустил релиз. Блокеров не было" label="Полный" />

          <div style={{ fontSize: 12, color: '#64748b', marginTop: 14, marginBottom: 8 }}>📅 С датой</div>
          <ExampleCard text="Вчера вечером энергия была 2, устал и не выспался" label="Прошедшая дата" />
          <ExampleCard text="Утренний чекин за понедельник: энергия 4, хорошее начало недели" label="День недели" />
        </div>
      ),
    },
  ]

  return (
    <div style={{
      height: '100%',
      overflowY: 'auto',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)',
      paddingBottom: 40,
    }}>
      {/* Хедер */}
      <div style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        background: 'rgba(15,23,42,0.92)',
        backdropFilter: 'blur(12px)',
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            background: 'rgba(255,255,255,0.08)',
            border: 'none',
            borderRadius: 10,
            width: 36,
            height: 36,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            color: '#94a3b8',
          }}
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <div style={{ fontWeight: 700, fontSize: 16, color: '#f1f5f9' }}>Инструкция по чекинам</div>
          <div style={{ fontSize: 12, color: '#64748b' }}>Как и когда заполнять</div>
        </div>
      </div>

      <div style={{ padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: 24 }}>

        {/* Вводный текст */}
        <GlassCard>
          <div style={{ padding: 16 }}>
            <div style={{ fontWeight: 600, fontSize: 15, color: '#f1f5f9', marginBottom: 8 }}>
              📋 Три слота каждый день
            </div>
            <p style={{ margin: 0, color: '#94a3b8', fontSize: 14, lineHeight: 1.6 }}>
              Чекины помогают отслеживать паттерны энергии и настроения. Отправляй голосовые или
              текстовые сообщения боту — он автоматически определит время и заполнит нужные поля.
            </p>
          </div>
        </GlassCard>

        {/* Слоты */}
        <div>
          <div style={{ fontSize: 13, color: '#64748b', fontWeight: 600, marginBottom: 10, paddingLeft: 4 }}>
            СЛОТЫ ЧЕКИНА
          </div>
          <Accordion items={slotItems} />
        </div>

        {/* Голосовой + примеры */}
        <div>
          <div style={{ fontSize: 13, color: '#64748b', fontWeight: 600, marginBottom: 10, paddingLeft: 4 }}>
            ГОЛОСОВЫЕ ЧЕКИНЫ
          </div>
          <Accordion items={voiceItems} />
        </div>

      </div>
    </div>
  )
}
