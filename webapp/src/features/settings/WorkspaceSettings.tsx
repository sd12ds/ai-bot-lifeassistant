import { useQuery } from "@tanstack/react-query"
import { fetchWorkspaces, fetchMembers } from "../../api/workspace"

export function WorkspaceSettings() {
  const { data: workspaces } = useQuery({ queryKey: ["workspaces"], queryFn: fetchWorkspaces })
  const wsId = workspaces?.[0]?.id
  const { data: members } = useQuery({ queryKey: ["members", wsId], queryFn: () => fetchMembers(wsId!), enabled: !!wsId })
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Workspace Settings</h1>
      {workspaces?.map((ws: any) => (
        <div key={ws.id} className="bg-[var(--bg-card)] rounded-xl p-4 border border-[var(--border)]">
          <div className="font-bold text-lg">{ws.name}</div>
          <div className="text-sm text-[var(--text-muted)]">Роль: {ws.role} | ID: {ws.id.slice(0, 8)}...</div>
        </div>
      ))}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border)]">
        <div className="p-4 border-b border-[var(--border)]"><h2 className="font-semibold">Участники</h2></div>
        <div className="divide-y divide-[var(--border)]">
          {members?.map((m: any) => (
            <div key={m.user_id} className="p-4 flex items-center justify-between">
              <span>User #{m.user_id}</span>
              <span className="px-2 py-0.5 rounded-full text-xs bg-[var(--bg-hover)] text-[var(--text-secondary)]">{m.role}</span>
            </div>
          )) || <div className="p-4 text-[var(--text-muted)]">Нет участников</div>}
        </div>
      </div>
    </div>
  )
}
