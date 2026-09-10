// Mirrors backend/app/schemas/*.py and the alerts route's hand-built dict.
// Keep these in sync when the API changes shape.

export type AnalysisType =
  | 'vegetation_stress'
  | 'land_change'
  | 'climate_impact'
  | 'infrastructure_change'
  | 'water_monitoring'

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
  vegetation_stress: 'Vegetation stress',
  land_change: 'Land change',
  climate_impact: 'Climate impact',
  infrastructure_change: 'Infrastructure change',
  water_monitoring: 'Water monitoring',
}
