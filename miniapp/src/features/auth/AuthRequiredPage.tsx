/**
 * Страница «Требуется авторизация».
 * Показывается когда пользователь открывает miniapp в браузере без JWT.
 * Предлагает получить ссылку через команду /web в боте.
 */
export function AuthRequiredPage() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', height: '100vh', padding: '2rem',
      textAlign: 'center', color: 'var(--tg-theme-text-color, #fff)',
      background: 'var(--tg-theme-bg-color, #1a1a2e)',
    }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🔒</div>
      <h2 style={{ marginBottom: '0.5rem' }}>Требуется авторизация</h2>
      <p style={{ opacity: 0.7, maxWidth: '320px', lineHeight: 1.5 }}>
        Откройте приложение через Telegram или запросите ссылку
        командой <strong>/web</strong> в боте.
      </p>
    </div>
  )
}
