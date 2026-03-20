import { useAuth } from '../hooks/useAuth'
import { LogOut } from 'lucide-react'

export function Header() {
  const { logout } = useAuth()
  return (
    <header className="h-14 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center justify-between px-6">
      <div className="text-sm text-[var(--text-muted)]">research.thalors.ai</div>
      <button onClick={logout} className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--error)] transition-colors">
        <LogOut size={16} /> Выйти
      </button>
    </header>
  )
}
