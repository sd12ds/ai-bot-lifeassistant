/**
 * API-клиент для Social Monitor домена.
 * Все запросы через общий apiClient с базовым URL /api.
 */
import { api } from './client'

export interface SocialSource {
  id: string
  platform: 'telegram' | 'instagram' | 'vk' | 'tiktok'
  source_url: string
  source_id: string
  source_name: string
  source_type: string
  status: 'active' | 'paused' | 'error'
  workspace_id: string | null
  collection_config: Record<string, any> | null
  schedule: Record<string, any> | null
  source_meta: Record<string, any> | null
  last_parsed_at: string | null
  error_count: number
  last_error: string | null
  created_at: string | null
}

export interface SocialPost {
  id: string
  source_id: string
  platform_post_id: string
  post_url: string | null
  post_type: string | null
  content: string | null
  posted_at: string | null
  author_name: string | null
  author_id: string | null
  metrics: {
    views?: number
    likes?: number
    comments?: number
    forwards?: number
    reactions?: Record<string, number>
    plays?: number
  } | null
  media_urls: string[] | null
  hashtags: string[] | null
  mentions: string[] | null
  location: Record<string, any> | null
}

export interface ParseRun {
  id: string
  source_id: string
  status: 'running' | 'completed' | 'failed'
  started_at: string | null
  finished_at: string | null
  posts_found: number
  posts_new: number
  error_details: string | null
  metrics: Record<string, any> | null
}

export interface SocialStats {
  total_sources: number
  active_sources: number
  error_sources: number
  paused_sources: number
  posts_this_week: number
}

export interface PostsResponse {
  total: number
  offset: number
  limit: number
  items: SocialPost[]
}

// ── Resolve URL ──────────────────────────────────────────────────────────────

export const resolveSourceUrl = async (url: string): Promise<SocialSource> => {
  const { data } = await api.post('/social/resolve', { url })
  return data
}

// ── Sources ──────────────────────────────────────────────────────────────────

export const fetchSources = async (platform?: string): Promise<SocialSource[]> => {
  const params = platform ? { platform } : {}
  const { data } = await api.get('/social/sources', { params })
  return data
}

export const fetchSource = async (id: string): Promise<SocialSource> => {
  const { data } = await api.get(`/social/sources/${id}`)
  return data
}

export const createSource = async (payload: {
  url: string
  collection_config?: Record<string, any>
  schedule?: Record<string, any>
}): Promise<SocialSource> => {
  const { data } = await api.post('/social/sources', payload)
  return data
}

export const updateSource = async (id: string, payload: Partial<SocialSource>): Promise<SocialSource> => {
  const { data } = await api.patch(`/social/sources/${id}`, payload)
  return data
}

export const deleteSource = async (id: string): Promise<void> => {
  await api.delete(`/social/sources/${id}`)
}

export const triggerParse = async (id: string): Promise<void> => {
  await api.post(`/social/sources/${id}/parse`)
}

// ── Posts ────────────────────────────────────────────────────────────────────

export const fetchSourcePosts = async (
  sourceId: string,
  params?: { offset?: number; limit?: number; search?: string; date_from?: string; date_to?: string; post_type?: string }
): Promise<PostsResponse> => {
  const { data } = await api.get(`/social/sources/${sourceId}/posts`, { params })
  return data
}

export const fetchRuns = async (sourceId: string): Promise<ParseRun[]> => {
  const { data } = await api.get(`/social/sources/${sourceId}/runs`)
  return data
}

export const fetchFeed = async (params?: {
  source_ids?: string
  platform?: string
  search?: string
  date_from?: string
  date_to?: string
  post_type?: string
  offset?: number
  limit?: number
}): Promise<PostsResponse> => {
  const { data } = await api.get('/social/feed', { params })
  return data
}

// ── Stats ────────────────────────────────────────────────────────────────────

export const fetchSocialStats = async (): Promise<SocialStats> => {
  const { data } = await api.get('/social/stats')
  return data
}
