import type {
  Alert,
  Analysis,
  AnalysisResult,
  AnalysisType,
  InferResponse,
  PipelineDescription,
  User,
} from './types'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

const TOKEN_STORAGE_KEY = 'aurora.token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY)
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new ApiError(response.status, typeof detail === 'string' ? detail : response.statusText)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  register: (input: { email: string; username: string; password: string; full_name?: string }) =>
    request<User>('/auth/register', { method: 'POST', body: JSON.stringify(input) }),

  login: (input: { username: string; password: string }) =>
    request<{ access_token: string; token_type: string }>('/auth/token', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  listAnalyses: () => request<Analysis[]>('/analysis/'),

  getAnalysis: (id: number) => request<Analysis>(`/analysis/${id}`),

  createAnalysis: (input: {
    analysis_type: AnalysisType
    latitude: number
    longitude: number
    radius_km: number
    description?: string
  }) => request<Analysis>('/analysis/', { method: 'POST', body: JSON.stringify(input) }),

  getAnalysisResults: (id: number) =>
    request<{ results: AnalysisResult[] }>(`/analysis/${id}/results`),

  listAlerts: (unreadOnly = false) =>
    request<Alert[]>(`/alerts${unreadOnly ? '?unread_only=true' : ''}`),

  acknowledgeAlert: (id: number) =>
    request<Alert>(`/alerts/${id}/acknowledge`, { method: 'POST' }),

  listPipelines: () => request<PipelineDescription[]>('/ai/pipelines'),

  infer: (input: {
    analysis_type: AnalysisType
    latitude: number
    longitude: number
    radius_km: number
    use_history?: boolean
    description?: string
  }) => request<InferResponse>('/ai/infer', { method: 'POST', body: JSON.stringify(input) }),

  requestPasswordReset: (email: string) =>
    request<{ detail: string }>('/auth/password-reset/request', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  confirmPasswordReset: (token: string, new_password: string) =>
    request<void>('/auth/password-reset/confirm', {
      method: 'POST',
      body: JSON.stringify({ token, new_password }),
    }),

  changePassword: (current_password: string, new_password: string) =>
    request<void>('/auth/password/change', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),
}
