import { api } from './client'

export interface WorkspaceInfo {
  id: string; name: string; owner_user_id: number; role: string; created_at?: string;
}

export const fetchWorkspaces = () => api.get<WorkspaceInfo[]>('/workspaces').then(r => r.data)
export const fetchMembers = (wsId: string) => api.get(`/workspaces/${wsId}/members`).then(r => r.data)
export const inviteMember = (wsId: string, userId: number, role: string) =>
  api.post(`/workspaces/${wsId}/invite`, { user_id: userId, role }).then(r => r.data)
export const updateMemberRole = (wsId: string, userId: number, role: string) =>
  api.patch(`/workspaces/${wsId}/members/${userId}`, { role }).then(r => r.data)
export const removeMember = (wsId: string, userId: number) =>
  api.delete(`/workspaces/${wsId}/members/${userId}`).then(r => r.data)
