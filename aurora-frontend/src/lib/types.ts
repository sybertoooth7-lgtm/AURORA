// Mirrors backend/app/schemas/*.py and the alerts route's hand-built dict.
// Keep these in sync when the API changes shape.

export type AnalysisType =
  | 'vegetation_stress'
  | 'land_change'
  | 'climate_impact'
  | 'infrastructure_change'
  | 'water_monitoring'
  | 'infrastructure_monitoring'
  | 'environmental_monitoring'
  | 'anomaly_detection'
  | 'wildfire_risk'
  | 'flood_monitoring'
  | 'insurance_index'
  | 'robotics_inspection'

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface User {
  id: number
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  email_verified: boolean
  created_at: string
}

// API keys (`/auth/api-keys`). `key` is the plaintext secret, shown exactly
// once at creation.
export interface ApiKeyCreated {
  id: number
  name: string
  prefix: string
  key: string
  expires_at: string | null
  created_at: string
}

export interface ApiKeyListEntry {
  id: number
  name: string
  prefix: string
  revoked: boolean
  expires_at: string | null
  created_at: string
  last_used_at: string | null
}

export interface ApiKeyListResponse {
  keys: ApiKeyListEntry[]
  total: number
}

// Robotics fleet (`/robotics`).
export interface FlightHealth {
  health_score: number
  status: string
  samples: number
  fault_count: number
  battery_min: number | null
}

export interface FlightSummary {
  flight_id: string
  started_at: string
  telemetry_count: number
  flight_health: FlightHealth
}

export interface FlightListResponse {
  flights: FlightSummary[]
  total: number
}

export interface TelemetryFrame {
  timestamp: number
  battery_percent: number | null
  gps_accuracy_m: number | null
  motor_temp_c: number | null
  altitude_m: number | null
  heading_deg: number | null
  faults: string[]
  sequence: number | null
  is_simulated: boolean
  level: string
}

export interface SimulateResponse extends FlightSummary {}

export interface RoboticsInspectResponse {
  result: PipelineResult
  analysis_id: number
  flight_id: string | null
  flight_health: FlightHealth | null
  vsatellite_damage_proxy: number | null
  combined_report: string[]
}

export interface Analysis {
  id: number
  user_id: number
  analysis_type: AnalysisType
  status: AnalysisStatus
  description: string | null
  latitude: number
  longitude: number
  radius_km: number
  created_at: string
  completed_at: string | null
  monitor_interval_minutes: number | null
  next_check_at: string | null
}

export interface AnalysisResultMetadata {
  source: string
  image_id: string
  acquired_at: string
  cloud_coverage: number
  resolution_m: number
  ndvi: number
  change_score: number
  // Present in results produced by the AI pipeline system (app/ai):
  provenance?: 'real' | 'simulated'
  simulated?: boolean
  model?: { name: string; version: string; kind: 'prototype' | 'production' }
  metrics?: Record<string, number>
  findings?: string[]
}

export interface AnalysisResult {
  id: number
  severity_score: number | null
  confidence: number | null
  finding: string
  metadata_json: string | null
  created_at: string
}

export interface Alert {
  id: number
  analysis_result_id: number
  alert_type: 'info' | 'warning' | 'critical'
  title: string
  description: string
  is_read: boolean
  created_at: string
  acknowledged_at: string | null
}

export function parseResultMetadata(result: AnalysisResult): AnalysisResultMetadata | null {
  if (!result.metadata_json) return null
  try {
    return JSON.parse(result.metadata_json) as AnalysisResultMetadata
  } catch {
    return null
  }
}

export const ANALYSIS_TYPE_LABELS: Record<AnalysisType, string> = {
  vegetation_stress: 'Vegetation Stress (Agriculture)',
  land_change: 'Land Change Detection',
  climate_impact: 'Climate Impact (Environmental)',
  infrastructure_change: 'Infrastructure Change',
  water_monitoring: 'Water Body Monitoring',
  infrastructure_monitoring: 'Infrastructure / Site Monitoring',
  environmental_monitoring: 'Environmental Monitoring (Water + Ecosystem)',
  anomaly_detection: 'Statistical Anomaly Detection',
  wildfire_risk: 'Wildfire Fuel / Dryness Risk',
  flood_monitoring: 'Flood / Inundation Monitoring',
  insurance_index: 'Crop Index (Parametric Insurance)',
  robotics_inspection: 'Robotics Field Inspection',
}

export interface PipelineDescription {
  name: string
  description: string
  handles: AnalysisType[]
  model: { name: string; version: string; kind: 'prototype' | 'production' }
  preprocessing: string[]
  data_requirements: { history_supported: boolean }
}

export interface PipelineResult {
  analysis_type: AnalysisType
  severity: number
  confidence: number
  findings: string[]
  metrics: Record<string, number>
  provenance: 'real' | 'simulated'
  simulated: boolean
  model: { name: string; version: string; kind: 'prototype' | 'production' }
  warning: string | null
  analysis_id?: number
}

export interface InferResponse {
  result: PipelineResult
  created_analysis_id: number
}

// Continuous-monitoring cadences. The numbers must stay <= the backend's
// MONITOR_MIN_INTERVAL_MINUTES floor and match what the API accepts.
export const MONITORING_CADENCES: Array<{ minutes: number; label: string }> = [
  { minutes: 60, label: 'Every hour' },
  { minutes: 1440, label: 'Every day' },
  { minutes: 10080, label: 'Every week' },
]

export function monitoringCadenceLabel(minutes: number | null): string {
  if (minutes == null) return 'Not monitoring'
  return (
    MONITORING_CADENCES.find((c) => c.minutes === minutes)?.label ?? `Every ${minutes} min`
  )
}
