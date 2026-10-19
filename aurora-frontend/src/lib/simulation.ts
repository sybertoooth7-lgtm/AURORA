// Mirrors backend/app/schemas/{simulation,spacecraft,space_division,
// mission_planning,multiplanetary,space_resources}.py.
//
// Everything here is Stage 0 model code: deterministic, offline, no hardware
// and no live space-domain data. The envelope types below are the reason the
// UI can say that in the same breath as the number.

export interface SimulationEnvelope {
  provenance: 'real' | 'simulated'
  stage: string
  model_limitations: string[]
}

export const STAGE_0_LABEL = 'Stage 0 simulation'

export interface SpacecraftSimulateRequest {
  altitude_km?: number
  inclination_deg?: number
  duration_s?: number
  dt_s?: number
  sample_points?: number
}

export interface SpacecraftSimulateResponse extends SimulationEnvelope {
  steps: number
  duration_s: number
  orbital_period_s: number
  velocity_kms: number
  eclipse_fraction: number
  battery_soc_min: number
  battery_soc_max: number
  battery_soc_end: number
  temperature_min_c: number
  temperature_max_c: number
  fsw_modes: string[]
  images_captured: number
  trajectory: Array<Record<string, unknown>>
}

export interface OrbitResponse extends SimulationEnvelope {
  altitude_km: number
  inclination_deg: number
  period_min: number
  velocity_kms: number
  eclipse_fraction_assumed: number
}

export interface LinkBudgetResponse extends SimulationEnvelope {
  frequency_mhz: number
  tx_power_dbm: number
  distance_km: number
  path_loss_db: number
  received_power_dbm: number
  snr_db: number
  max_range_km_at_10db: number
}

export interface PlaneInput {
  inclination_deg?: number
  altitude_km?: number
  raan_deg?: number
}

export interface SatelliteInput {
  id: string
  name?: string
  plane: PlaneInput
  phase_deg?: number
  status?: 'commissioning' | 'operational' | 'degraded' | 'decommissioned'
  priority?: number
}

export interface PlaneSummary {
  inclination_deg: number
  altitude_km: number
  raan_deg: number
  period_min: number
  satellites: number
}

export interface ConstellationEvaluateResponse extends SimulationEnvelope {
  name: string
  satellites: number
  operational: number
  planes: PlaneSummary[]
  revisit_interval_hours: number | null
}

export interface ContactRequestInput {
  satellite_id: string
  priority?: number
  ground_station: string
  start_s: number
  end_s: number
  max_elevation_deg?: number
  slant_range_km?: number
}

export interface GroundContactScheduleResponse extends SimulationEnvelope {
  requested: number
  granted: Array<{
    satellite_id: string
    ground_station: string
    start_s: number
    end_s: number
    duration_s: number
    max_elevation_deg: number
    slant_range_km: number
  }>
  conflicts: Array<{
    satellite_id: string
    ground_station: string
    start_s: number
    end_s: number
    reason: string
  }>
}

export type TaskPriorityName = 'low' | 'normal' | 'high' | 'critical'

export interface TaskInput {
  id: string
  name?: string
  priority?: TaskPriorityName
  earliest_start_s?: number
  latest_finish_s: number
  duration_s: number
  resource_requirements?: Record<string, number>
  requires_contact?: boolean
}

export interface ScheduleResponse extends SimulationEnvelope {
  scheduled: Array<{
    id: string
    name: string
    priority: TaskPriorityName
    start_s: number
    end_s: number
    requires_contact: boolean
  }>
  conflicts: Array<{
    id: string
    name: string
    priority: TaskPriorityName
    reason: string
  }>
  window_start_s: number
  window_end_s: number
}

export interface DataSourceReadiness {
  name: string
  provider: string
  status: 'healthy' | 'degraded' | 'down' | 'unknown'
  quota_used: number
  quota_limit: number | null
  quota_fraction_used: number | null
  schedulable: boolean
}

export interface DataReadinessResponse extends SimulationEnvelope {
  overall: string
  basis: string
  sources: DataSourceReadiness[]
  observations: Record<string, number>
}

export interface MissionContextInput {
  timestamp?: number
  environment?: string
  target_body?: string
  autonomy_level?: number
  one_way_delay_s?: number
  in_contact?: boolean
  battery_percent?: number
  power_available_w?: number
  power_demand_w?: number
  temperature_c?: number
  inventory?: Record<string, number>
  environment_sensor?: Record<string, unknown>
}

export interface StackAction {
  layer: string
  action_type: string
  target: string
  description: string
  requires_authorization: boolean
  reversible: boolean
  severity: string
}

export interface StackDecisionResponse extends SimulationEnvelope {
  layers_evaluated: string[]
  approved: StackAction[]
  pending_authorization: StackAction[]
  rejected: StackAction[]
  safe_mode_active: boolean
  warnings: string[]
}

export interface EnvironmentProfile {
  name: string
  gravity_ms2: number
  atmosphere_pressure_pa: number
  has_atmosphere: boolean
  solar_flux_wm2: number
  mean_temperature_c: number
  temperature_range_c: [number, number]
  day_length_s: number
  radiation_multiplier: number
  terrain_roughness: number
  slope_range_deg: [number, number]
  regolith_depth_m: number
}

export interface EnvironmentListResponse extends SimulationEnvelope {
  environments: EnvironmentProfile[]
}

export interface EnvironmentDetailResponse extends SimulationEnvelope {
  environment: EnvironmentProfile
}

export type CommsTarget =
  | 'earth_leo'
  | 'moon'
  | 'mars'
  | 'jupiter'
  | 'saturn'
  | 'asteroid'
  | 'deep_space'

export interface CommsDelayResponse extends SimulationEnvelope {
  target_body: string
  owlt_s: number
  rtt_s: number
  autonomy_level: number
  real_time: boolean
  recommended_contact_interval_s: number
  max_autonomous_operations_s: number
}

export interface Technology {
  id: string
  name: string
  resource_type: string
  trl: number
  readiness: string
  mass_kg: number
  power_w: number
  production_kg_per_day: number
  production_efficiency: number
  risk_overall: number
  total_timeline_years: number
  target_body: string
  terrestrial_heritage: string
}

export interface TechnologyListResponse extends SimulationEnvelope {
  count: number
  technologies: Technology[]
}

export interface TechnologyDetailResponse extends Technology, SimulationEnvelope {
  description: string
  hardware: string[]
  dependency_ids: string[]
  dependency_chain: string[]
  risk: Record<string, number>
  timeline_years: Record<string, number>
}

export interface EconomicsResponse extends SimulationEnvelope {
  resource_type: string
  mass_kg: number
  destination: string
  earth_launch_cost: number
  in_situ_cost: number
  savings: number
  savings_percent: number
  profile: Record<string, number>
}

export type ExtractionProcess =
  | 'water_ice'
  | 'oxygen_regolith'
  | 'metals'
  | 'construction_material'
  | 'generic'

export interface ExtractionResponse extends SimulationEnvelope {
  process: ExtractionProcess
  resource_type: string
  hours: number
  feedstock_kg: number
  mass_produced_kg: number
  mass_waste_kg: number
  energy_used_wh: number
  yield_fraction: number
  specific_energy_kwh_per_kg: number | null
  status: string
}

export interface SiteOccurrenceInput {
  resource_type: string
  significance?: 'primary' | 'secondary' | 'trace'
  estimated_mass_kg: number
  concentration_fraction?: number
  depth_m?: number
  extraction_method?: string
}

export interface SiteInput {
  id: string
  name?: string
  body: string
  coordinates?: Record<string, number>
  resources: SiteOccurrenceInput[]
  terrain_difficulty?: number
  solar_power_availability?: number
  access_window_hours?: number
  priority?: 'low' | 'medium' | 'high'
}

export interface ProspectingResponse extends SimulationEnvelope {
  ranked: Array<{
    id: string
    name: string
    body: string
    value_score: number
    total_mass_kg: number
    primary_resources: string[]
    viability: Array<{
      resource_type: string
      significance: string
      estimated_mass_kg: number
      viability: number
    }>
  }>
  summary: Record<string, unknown>
}

export interface RoadmapResponse extends SimulationEnvelope {
  total_milestones: number
  total_cost_usd: number
  total_duration_years: number
  critical_path_milestones: number
  phases: Array<{
    phase: string
    phase_number: number
    milestone_count: number
    critical_milestones: number
    total_cost_usd: number
    duration_years: number
    start_year: number
    end_year: number
  }>
  milestones: Array<Record<string, unknown>>
}
