import type {
  Alert,
  Analysis,
  AnalysisHistoryResponse,
  AnalysisListQuery,
  AnalysisListResponse,
  AnalysisResult,
  AnalysisSummaryResponse,
  AnalysisType,
  ApiKeyCreated,
  ApiKeyListEntry,
  ApiKeyListResponse,
  CropAnalysisResponse,
  CropBulkAnalysisResponse,
  FieldBoundary,
  FlightListResponse,
  FlightSummary,
  InferResponse,
  JobPipelineStatus,
  PipelineDescription,
  RoboticsInspectResponse,
  SimulateResponse,
  TelemetryFrame,
  User,
} from './types'
import type {
  CommsDelayResponse,
  CommsTarget,
  ConstellationEvaluateResponse,
  ContactRequestInput,
  DataReadinessResponse,
  EconomicsResponse,
  EnvironmentDetailResponse,
  EnvironmentListResponse,
  ExtractionProcess,
  ExtractionResponse,
  GroundContactScheduleResponse,
  LinkBudgetResponse,
  MissionContextInput,
  OrbitResponse,
  ProspectingResponse,
  RoadmapResponse,
  ScheduleResponse,
  SatelliteInput,
  SiteInput,
  SpacecraftSimulateResponse,
  StackDecisionResponse,
  TaskInput,
  TechnologyDetailResponse,
  TechnologyListResponse,
} from './simulation'

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

/**
 * Turn a FastAPI error body into one readable line.
 *
 * A 422 carries a list of pydantic errors rather than a sentence, and a
 * division endpoint rejects a lot of malformed input, so the field and the
 * reason are worth more to a user than "Unprocessable Entity".
 */
function describeDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (!Array.isArray(detail)) return null
  const lines = detail
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const entry = item as { loc?: unknown; msg?: unknown }
      const where = Array.isArray(entry.loc)
        ? entry.loc.filter((part) => typeof part === 'string').join('.')
        : ''
      if (typeof entry.msg !== 'string') return null
      return where ? `${where}: ${entry.msg}` : entry.msg
    })
    .filter((line): line is string => line !== null)
  return lines.length > 0 ? lines.join('; ') : null
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
      // The API's 422 handler keeps `detail` as a fixed sentence and puts the
      // per-field problems under `errors`, so look there first or every
      // malformed division input reads as "Request validation failed".
      const reasons =
        body.code === 'validation_failed' ? describeDetail(body.errors) : null
      detail = reasons ?? describeDetail(body.detail) ?? detail
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

function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    search.set(key, String(value))
  }
  const encoded = search.toString()
  return encoded ? `?${encoded}` : ''
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

  listAnalyses: (query: AnalysisListQuery = {}) =>
    request<AnalysisListResponse>(`/analysis/${qs({ ...query })}`),

  analysisSummary: () => request<AnalysisSummaryResponse>('/analysis/summary'),

  analysisHistory: (id: number) =>
    request<AnalysisHistoryResponse>(`/analysis/${id}/history`),

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

  // Field-boundary crop analysis: the revenue product, and the only surface
  // that takes a polygon rather than a point plus radius.
  analyzeField: (input: {
    field_boundary: FieldBoundary
    use_history?: boolean
    description?: string
  }) => request<CropAnalysisResponse>('/crop/analyze', { method: 'POST', body: JSON.stringify(input) }),

  analyzeFields: (input: {
    fields: Array<{ label?: string | null; field_boundary: FieldBoundary }>
    use_history?: boolean
  }) =>
    request<CropBulkAnalysisResponse>('/crop/analyze/bulk', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  // Operators only: 403 for a normal account.
  jobPipelineStatus: () => request<JobPipelineStatus>('/system/jobs'),

  dataReadiness: () => request<DataReadinessResponse>('/mission-planning/data-readiness'),

  // ---- Spacecraft (Stage 0 simulation) ----
  simulateSpacecraft: (input: {
    altitude_km?: number
    inclination_deg?: number
    duration_s?: number
    dt_s?: number
    sample_points?: number
  }) =>
    request<SpacecraftSimulateResponse>('/spacecraft/simulate', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  orbitProperties: (input: { altitude_km?: number; inclination_deg?: number } = {}) =>
    request<OrbitResponse>(`/spacecraft/orbit${qs({ ...input })}`),

  linkBudget: (
    input: {
      distance_km?: number
      frequency_mhz?: number
      tx_power_dbm?: number
      rx_gain_dbi?: number
    } = {},
  ) => request<LinkBudgetResponse>(`/spacecraft/link-budget${qs({ ...input })}`),

  // ---- Space Division (Stage 0 simulation) ----
  evaluateConstellation: (input: { name?: string; satellites: SatelliteInput[] }) =>
    request<ConstellationEvaluateResponse>('/space-division/constellation', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  scheduleGroundContacts: (requests: ContactRequestInput[]) =>
    request<GroundContactScheduleResponse>('/space-division/ground-contacts', {
      method: 'POST',
      body: JSON.stringify({ requests }),
    }),

  // ---- Mission Planning ----
  buildSchedule: (input: {
    tasks: TaskInput[]
    budgets?: Array<{ name: string; capacity: number; unit?: string }>
    contact_windows?: Array<{
      ground_station?: string
      start_s: number
      end_s: number
      max_elevation_deg?: number
      slant_range_km?: number
    }>
  }) =>
    request<ScheduleResponse>('/mission-planning/schedule', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  // ---- Multi-Planetary autonomy (Stage 0 simulation) ----
  decideStack: (context: MissionContextInput) =>
    request<StackDecisionResponse>('/multiplanetary/decide', {
      method: 'POST',
      body: JSON.stringify(context),
    }),

  listEnvironments: () => request<EnvironmentListResponse>('/multiplanetary/environments'),

  getEnvironment: (name: string) =>
    request<EnvironmentDetailResponse>(`/multiplanetary/environments/${name}`),

  commsDelay: (target: CommsTarget) =>
    request<CommsDelayResponse>(`/multiplanetary/comms-delay/${target}`),

  // ---- Space Resources / ISRU (Stage 0 simulation) ----
  listTechnologies: (
    query: {
      target_body?: string
      resource_type?: string
      min_trl?: number
      max_trl?: number
    } = {},
  ) => request<TechnologyListResponse>(`/space-resources/technologies${qs({ ...query })}`),

  technologyDetail: (id: string) =>
    request<TechnologyDetailResponse>(`/space-resources/technologies/${id}`),

  deliveryEconomics: (
    resourceType: string,
    query: { mass_kg?: number; destination?: string } = {},
  ) =>
    request<EconomicsResponse>(
      `/space-resources/economics/${resourceType}${qs({ ...query })}`,
    ),

  simulateExtraction: (input: {
    process?: ExtractionProcess
    hours?: number
    feedstock_kg?: number
    power_w?: number
    efficiency?: number
  }) =>
    request<ExtractionResponse>('/space-resources/extraction', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  rankProspectSites: (input: { sites: SiteInput[]; body?: string }) =>
    request<ProspectingResponse>('/space-resources/prospecting', {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  programRoadmap: () => request<RoadmapResponse>('/space-resources/roadmap'),
}
