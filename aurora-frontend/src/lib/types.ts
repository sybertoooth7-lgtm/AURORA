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

export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface User {
  id: number
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  created_at: string
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
