import { api } from './client'

// Типы
export interface Job {
  id: string; title: string; description?: string; status: string;
  job_type: string; provider: string; origin: string; visibility: string;
  created_by: number; created_at?: string; updated_at?: string; last_run_at?: string;
}
export interface ResultItem {
  id: string; source_url?: string; domain?: string; title?: string;
  extracted_fields?: Record<string, any>; dedupe_hash?: string;
}
export interface Run { id: string; job_id: string; status: string; started_at?: string; finished_at?: string; metrics?: any; error_details?: string; }
export interface Stats { total_jobs: number; running: number; completed: number; failed: number; draft: number; canceled: number; total_results: number; }

// API функции
export const fetchStats = () => api.get<Stats>('/research/stats').then(r => r.data)
export const fetchJobs = (params?: any) => api.get<Job[]>('/research/jobs', { params }).then(r => r.data)
export const fetchJob = (id: string) => api.get<Job>(`/research/jobs/${id}`).then(r => r.data)
export const createJob = (data: any) => api.post<Job>('/research/jobs', data).then(r => r.data)
export const runJob = (id: string) => api.post(`/research/jobs/${id}/run`).then(r => r.data)
export const cancelJob = (id: string) => api.post(`/research/jobs/${id}/cancel`).then(r => r.data)
export const deleteJob = (id: string) => api.delete(`/research/jobs/${id}`).then(r => r.data)
export const duplicateJob = (id: string) => api.post(`/research/jobs/${id}/duplicate`).then(r => r.data)
export const fetchResults = (jobId: string, params?: any) => api.get(`/research/jobs/${jobId}/results`, { params }).then(r => r.data)
export const fetchRuns = (jobId: string) => api.get<Run[]>(`/research/jobs/${jobId}/runs`).then(r => r.data)
export const fetchSources = (jobId: string) => api.get(`/research/jobs/${jobId}/sources`).then(r => r.data)
export const exportResults = (jobId: string, format = 'json') => api.post(`/research/jobs/${jobId}/export`, null, { params: { format } }).then(r => r.data)
