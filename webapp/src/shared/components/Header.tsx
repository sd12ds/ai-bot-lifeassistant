import { useAuth } from '../hooks/useAuth'
import { useQuery } from '@tanstack/react-query'
import { fetchWorkspaces } from '../../api/workspace'
import { LogOut, Building2 } from 'lucide-react'
import { QuotaIndicator } from './QuotaIndicator'
import { useState } from 'react'

export function Header() {
  const { logout } = useAuth()
  const { data: workspaces } = useQuery({ queryKey: ['workspaces'], queryFn: fetchWorkspaces })
  const [currentWs, _setCurrentWs] = useState<string>("")

  // Автовыбор первого workspace
  const activeWs = workspaces?.find(w => w.id === currentWs) || workspaces?.[0]

  return (
    <header className="h-14 bg-[var(--bg-secondary)] border-b border-[var(--border)] flex items-center justify-between px-6">
      <div className="flex items-center gap-3">
        {activeWs && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg-card)] rounded-lg border border-[var(--border)]">
            <Building2 size={14} className="text-[var(--accent)]" />
            <span className="text-sm font-medium">{activeWs.name}</span>
            <span className="text-xs text-[var(--text-muted)]">({activeWs.role})</span>
          </div>
        )}
        <QuotaIndicator />
        <span className="text-sm text-[var(--text-muted)]">research.thalors.ai</span>
      </div>
      <button onClick={logout} className="flex items-center gap-2 text-sm text-[var(--text-muted)] hover:text-[var(--error)] transition-colors">
        <LogOut size={16} /> Выйти
      </button>
    </header>
  )
}
