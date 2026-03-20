import { useLocation, useNavigate } from 'react-router-dom'
import { LayoutDashboard, List, FileText, Settings, Search, CreditCard } from 'lucide-react'

const NAV = [
  { path: '/research', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/research/jobs', icon: List, label: 'Задачи' },
  { path: '/research/jobs/new', icon: Search, label: 'Новая задача' },
  { path: '/research/templates', icon: FileText, label: 'Шаблоны' },
  { path: '/billing', icon: CreditCard, label: 'Billing' },
  { path: '/settings', icon: Settings, label: 'Audit' },
  { path: '/settings/workspace', icon: Settings, label: 'Workspace' },
]

export function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  return (
    <aside className="w-60 h-screen bg-[var(--bg-secondary)] border-r border-[var(--border)] flex flex-col p-4 gap-1">
      <div className="text-xl font-bold text-[var(--accent)] mb-6 px-3">Research</div>
      {NAV.map(item => {
        const active = location.pathname === item.path || (item.path !== '/research' && location.pathname.startsWith(item.path))
        const Icon = item.icon
        return (
          <button key={item.path} onClick={() => navigate(item.path)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors w-full text-left
              ${active ? 'bg-[var(--accent)]/15 text-[var(--accent)]' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'}`}>
            <Icon size={18} />
            {item.label}
          </button>
        )
      })}
    </aside>
  )
}
