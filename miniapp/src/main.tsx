/**
 * Точка входа React-приложения.
 * Импортирует глобальные стили (Tailwind + тема + CSS vars).
 */
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/theme.css'
import './styles/globals.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
