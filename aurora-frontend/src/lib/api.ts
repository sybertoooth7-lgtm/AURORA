import type {
  Alert,
  Analysis,
  AnalysisResult,
  AnalysisType,
  ApiKeyCreated,
  ApiKeyListEntry,
  ApiKeyListResponse,
  FlightListResponse,
  FlightSummary,
  InferResponse,
  PipelineDescription,
  RoboticsInspectResponse,
  SimulateResponse,
  TelemetryFrame,
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

const SESSION_EXPIRED_KEY = 'aurora.sessionExpired'

export function consumeSessionExpiredFlag(): boolean {
  const expired = localStorage.getItem(SESSION_EXPIRED_KEY) === '1'
  if (expired) localStorage.removeItem(SESSION_EXPIRED_KEY)
  return expired
}

// Set by AuthProvider so a 401 on an authenticated request can force a
// logout + redirect-to-login, without api.ts importing React/router
// directly. A 401 on /auth/token itself (wrong password) does NOT go
// through this -- see the `token` check in request() below -- that's a
// normal login failure, not an expired session.
let onSessionExpired: (() => void) | null = null

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(
  path: string,
  options: RequestInit & { skipSessionExpiredHandling?: boolean } = {},
): Promise<T> {
  const { skipSessionExpiredHandling, ...fetchOptions } = options
  const token = getToken()
  const headers = new Headers(fetchOptions.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path}`, { ...fetchOptions, headers })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // response wasn't JSON -- fall back to statusText
    }

    // Only treat this as an expired session if we WERE sending a token --
    // a 401 from /auth/token itself (wrong password, no token sent yet)
    // is just a normal failed login, not a session that died. A caller
    // can also opt out entirely (see api.changePassword) for an endpoint
    // where a 401 can mean something other than "your token is bad".
    if (response.status === 401 && token && !skipSessionExpiredHandling) {
      localStorage.setItem(SESSION_EXPIRED_KEY, '1')
      onSessionExpired?.()
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

  me: () => request<User>('/auth/me'),

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

  setMonitoring: (id: number, monitorIntervalMinutes: number | null) =>
    request<Analysis>(`/analysis/${id}/monitor`, {
      method: 'PATCH',
      body: JSON.stringify({ monitor_interval_minutes: monitorIntervalMinutes }),
    }),

  rerunAnalysis: (id: number) =>
    request<Analysis>(`/analysis/${id}/re-run`, { method: 'POST' }),

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
      skipSessionExpiredHandling: true,
    }),

  confirmEmailVerification: (token: string) =>
    request<void>('/auth/verify-email/confirm', { method: 'POST', body: JSON.stringify({ token }) }),

  resendEmailVerification: () =>
    request<{ detail: string }>('/auth/verify-email/resend', { method: 'POST' }),

  listApiKeys: () => request<ApiKeyListResponse>('/auth/api-keys'),

  createApiKey: (input: { name: string; expires_days?: number }) =>
    request<ApiKeyCreated>('/auth/api-keys', { method: 'POST', body: JSON.stringify(input) }),

  revokeApiKey: (id: number) =>
    request<ApiKeyListEntry>(`/auth/api-keys/${id}/revoke`, { method: 'POST' }),

  listFlights: () => request<FlightListResponse>('/robotics/flights'),

  getFlight: (id: string) => request<FlightSummary>(`/robotics/flights/${id}`),

  getFlightTelemetry: (id: string, limit = 200) =>
    request<TelemetryFrame[]>(`/robotics/flights/${id}/telemetry?limit=${limit}`),

  simulateFlight: (input: {
    latitude: number
    longitude: number
    radius_km: number
    num_frames: number
  }) => request<SimulateResponse>('/robotics/simulate', { method: 'POST', body: JSON.stringify(input) }),

  inspectFlightArea: (input: {
    latitude: number
    longitude: number
    radius_km: number
    use_history?: boolean
    flight_id?: string
    description?: string
  }) =>
    request<RoboticsInspectResponse>('/robotics/inspect', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
}
