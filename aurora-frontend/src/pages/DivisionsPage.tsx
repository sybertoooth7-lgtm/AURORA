import { useCallback, useEffect, useState } from 'react'
import { ErrorNote, ProvenanceBadge, Readout, SimulationPanel, describeApiError } from '../components/SimulationPanel'
import { api } from '../lib/api'
import type {
  CommsDelayResponse,
  CommsTarget,
  ConstellationEvaluateResponse,
  ContactRequestInput,
  EconomicsResponse,
  EnvironmentListResponse,
  ExtractionProcess,
  ExtractionResponse,
  GroundContactScheduleResponse,
  LinkBudgetResponse,
  OrbitResponse,
  RoadmapResponse,
  SatelliteInput,
  ScheduleResponse,
  SpacecraftSimulateResponse,
  StackDecisionResponse,
  TechnologyListResponse,
} from '../lib/simulation'

/**
 * The division surfaces: spacecraft, constellation, mission planning, autonomy
 * and ISRU. Every panel here runs Stage 0 model code, so every panel is drawn
 * through SimulationPanel and shows what its model leaves out. Nothing on this
 * page commands hardware or reads telemetry.
 */

const TABS = [
  { id: 'spacecraft', label: 'Spacecraft' },
  { id: 'fleet', label: 'Constellation' },
  { id: 'planning', label: 'Mission planning' },
  { id: 'autonomy', label: 'Autonomy stack' },
  { id: 'resources', label: 'Space resources' },
] as const

type TabId = (typeof TABS)[number]['id']

function useSim<T>() {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const run = useCallback(async (fn: () => Promise<T>) => {
    setRunning(true)
    setError(null)
    try {
      setData(await fn())
    } catch (err) {
      setError(describeApiError(err, 'The run failed.'))
    } finally {
      setRunning(false)
    }
  }, [])

  return { data, error, running, run }
}

function NumberInput({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  suffix,
}: {
  label: string
  value: number
  onChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  suffix?: string
}) {
  return (
    <label className="block">
      <span className="text-xs text-[var(--color-ink-soft)]">
        {label}
        {suffix ? ` (${suffix})` : ''}
      </span>
      <input
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => onChange(Number(event.target.value))}
        className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-2 py-1.5 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
      />
    </label>
  )
}

function Choice({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: Array<{ value: string; label: string }>
}) {
  return (
    <label className="block">
      <span className="text-xs text-[var(--color-ink-soft)]">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-2 py-1.5 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function RunButton({
  onClick,
  running,
  label,
}: {
  onClick: () => void
  running: boolean
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={running}
      className="rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
    >
      {running ? 'Running…' : label}
    </button>
  )
}

function Grid({ children, columns = 4 }: { children: React.ReactNode; columns?: number }) {
  const widths: Record<number, string> = {
    2: 'grid-cols-2',
    3: 'grid-cols-2 sm:grid-cols-3',
    4: 'grid-cols-2 sm:grid-cols-4',
    5: 'grid-cols-2 sm:grid-cols-5',
  }
  return <div className={`mt-4 grid gap-4 ${widths[columns] ?? widths[4]}`}>{children}</div>
}

function Controls({ children }: { children: React.ReactNode }) {
  return <div className="grid gap-3 sm:grid-cols-4">{children}</div>
}

function fmt(value: number | null | undefined, digits = 3): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

export function DivisionsPage() {
  const [tab, setTab] = useState<TabId>('spacecraft')

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header>
        <h1 className="font-[var(--font-display)] text-2xl font-semibold">Division simulations</h1>
        <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-soft)]">
          The spacecraft, constellation, mission-planning, autonomy and ISRU engines, exposed as
          planning tools. They are architecture and hand-entered model code: no hardware, no live
          space-domain telemetry, no contracted prices. Each panel carries its own provenance flag
          and the list of what its model ignores.
        </p>
      </header>

      <div className="mt-6 flex flex-wrap gap-1 border-b border-[var(--color-border)]">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            onClick={() => setTab(entry.id)}
            className={`rounded-t-sm px-4 py-2 text-sm ${
              tab === entry.id
                ? 'bg-[var(--color-paper-raised)] font-semibold text-[var(--color-ink)]'
                : 'text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]'
            }`}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="mt-6 space-y-8">
        {tab === 'spacecraft' && <SpacecraftTab />}
        {tab === 'fleet' && <FleetTab />}
        {tab === 'planning' && <PlanningTab />}
        {tab === 'autonomy' && <AutonomyTab />}
        {tab === 'resources' && <ResourcesTab />}
      </div>
    </div>
  )
}

function SpacecraftTab() {
  const sim = useSim<SpacecraftSimulateResponse>()
  const orbit = useSim<OrbitResponse>()
  const link = useSim<LinkBudgetResponse>()

  const [altitude, setAltitude] = useState(500)
  const [inclination, setInclination] = useState(97.4)
  const [duration, setDuration] = useState(5550)
  const [dt, setDt] = useState(20)
  const [distance, setDistance] = useState(1200)
  const [frequency, setFrequency] = useState(435)

  const runAll = useCallback(() => {
    void sim.run(() =>
      api.simulateSpacecraft({
        altitude_km: altitude,
        inclination_deg: inclination,
        duration_s: duration,
        dt_s: dt,
        sample_points: 8,
      }),
    )
    void orbit.run(() => api.orbitProperties({ altitude_km: altitude, inclination_deg: inclination }))
    void link.run(() => api.linkBudget({ distance_km: distance, frequency_mhz: frequency }))
  }, [sim, orbit, link, altitude, inclination, duration, dt, distance, frequency])

  // Mount only. runAll's identity changes with every response it stores, so
  // depending on it makes the run re-fire itself forever; the Run button is
  // what applies changed inputs.
  useEffect(() => {
    runAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const result = sim.data
  const kepler = orbit.data

  return (
    <>
      <Controls>
        <NumberInput label="Altitude" value={altitude} onChange={setAltitude} min={200} max={2000} suffix="km" />
        <NumberInput label="Inclination" value={inclination} onChange={setInclination} min={0} max={180} step={0.1} suffix="deg" />
        <NumberInput label="Window" value={duration} onChange={setDuration} min={60} max={86400} step={60} suffix="s" />
        <NumberInput label="Step" value={dt} onChange={setDt} min={1} max={600} step={1} suffix="s" />
        <NumberInput label="Slant range" value={distance} onChange={setDistance} min={1} max={40000} step={50} suffix="km" />
        <NumberInput label="Frequency" value={frequency} onChange={setFrequency} min={100} max={8000} step={5} suffix="MHz" />
        <div className="sm:col-span-2">
          <RunButton onClick={runAll} running={sim.running || orbit.running || link.running} label="Run subsystem sweep" />
        </div>
      </Controls>

      {(sim.error || orbit.error || link.error) && (
        <ErrorNote message={sim.error ?? orbit.error ?? link.error ?? ''} />
      )}

      <SimulationPanel
        title="Coupled subsystem run"
        description="ADCS, power, thermal, flight software and payload integrated over one window."
        envelope={result}
      >
        {!result ? (
          <p className="text-sm text-[var(--color-ink-soft)]">No run yet.</p>
        ) : (
          <>
            <Grid columns={5}>
              <Readout label="Steps" value={String(result.steps)} />
              <Readout label="Period" value={`${fmt(result.orbital_period_s, 0)} s`} />
              <Readout label="Velocity" value={`${fmt(result.velocity_kms, 3)} km/s`} />
              <Readout label="Shadow" value={`${(result.eclipse_fraction * 100).toFixed(1)}%`} />
              <Readout label="Images" value={String(result.images_captured)} />
            </Grid>
            <Grid columns={4}>
              <Readout
                label="Battery"
                value={`${fmt(result.battery_soc_min, 1)} → ${fmt(result.battery_soc_end, 1)}%`}
              />
              <Readout label="Battery peak" value={`${fmt(result.battery_soc_max, 1)}%`} />
              <Readout label="Temperature" value={`${fmt(result.temperature_min_c, 1)} to ${fmt(result.temperature_max_c, 1)} °C`} />
              <Readout label="FSW modes" value={result.fsw_modes.join(' · ') || '—'} />
            </Grid>
            <p className="font-tabular mt-4 text-xs text-[var(--color-ink-soft)]">
              trajectory sampled to {result.trajectory.length} states
            </p>
          </>
        )}
      </SimulationPanel>

      <div className="grid gap-8 lg:grid-cols-2">
        <SimulationPanel
          title="Keplerian orbit"
          description="The third-law period and velocity the fleet planner also uses."
          envelope={kepler}
        >
          {!kepler ? (
            <p className="text-sm text-[var(--color-ink-soft)]">No data.</p>
          ) : (
            <>
              <Grid columns={2}>
                <Readout label="Period" value={`${fmt(kepler.period_min, 2)} min`} />
                <Readout label="Velocity" value={`${fmt(kepler.velocity_kms, 3)} km/s`} />
              </Grid>
              {result && (
                <p className="font-tabular mt-4 text-xs text-[var(--color-stress)]">
                  The coupled run holds its period at {fmt(result.orbital_period_s, 0)} s whatever the
                  altitude; Kepler says {fmt(kepler.period_min, 2)} min at {kepler.altitude_km} km.
                </p>
              )}
            </>
          )}
        </SimulationPanel>

        <SimulationPanel title="Link budget" description="Free-space only, for one slant range." envelope={link.data}>
          {!link.data ? (
            <p className="text-sm text-[var(--color-ink-soft)]">No data.</p>
          ) : (
            <Grid columns={2}>
              <Readout label="Path loss" value={`${fmt(link.data.path_loss_db, 2)} dB`} />
              <Readout label="Received" value={`${fmt(link.data.received_power_dbm, 2)} dBm`} />
              <Readout label="SNR" value={`${fmt(link.data.snr_db, 2)} dB`} />
              <Readout label="Max range at 10 dB" value={`${fmt(link.data.max_range_km_at_10db, 1)} km`} />
            </Grid>
          )}
        </SimulationPanel>
      </div>
    </>
  )
}

function FleetTab() {
  const fleet = useSim<ConstellationEvaluateResponse>()
  const contacts = useSim<GroundContactScheduleResponse>()

  const [planes, setPlanes] = useState(4)
  const [perPlane, setPerPlane] = useState(3)
  const [altitude, setAltitude] = useState(500)
  const [inclination, setInclination] = useState(97.4)
  const [station, setStation] = useState('gs-0')
  const [contenders, setContenders] = useState(3)

  const runAll = useCallback(() => {
    const safePlanes = Math.max(1, Math.min(12, Math.round(planes)))
    const safePer = Math.max(1, Math.min(24, Math.round(perPlane)))
    const satellites: SatelliteInput[] = []
    for (let plane = 0; plane < safePlanes; plane += 1) {
      for (let index = 0; index < safePer; index += 1) {
        satellites.push({
          id: `sat-${plane + 1}-${index + 1}`,
          plane: {
            inclination_deg: inclination,
            altitude_km: altitude,
            raan_deg: (plane * 360) / safePlanes,
          },
          phase_deg: (index * 360) / safePer,
        })
      }
    }
    void fleet.run(() => api.evaluateConstellation({ name: 'aurora-earth', satellites }))

    const safeContenders = Math.max(1, Math.min(20, Math.round(contenders)))
    const requests: ContactRequestInput[] = Array.from(
      { length: safeContenders },
      (_, index) => ({
        satellite_id: `sat-${index + 1}`,
        priority: safeContenders - index,
        ground_station: station || 'gs-0',
        start_s: 60 * index,
        end_s: 60 * index + 90,
      }),
    )
    void contacts.run(() => api.scheduleGroundContacts(requests))
  }, [fleet, contacts, planes, perPlane, altitude, inclination, station, contenders])

  // Mount only. runAll's identity changes with every response it stores, so
  // depending on it makes the run re-fire itself forever; the Run button is
  // what applies changed inputs.
  useEffect(() => {
    runAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <Controls>
        <NumberInput label="Planes" value={planes} onChange={setPlanes} min={1} max={12} />
        <NumberInput label="Satellites per plane" value={perPlane} onChange={setPerPlane} min={1} max={24} />
        <NumberInput label="Altitude" value={altitude} onChange={setAltitude} min={200} max={2000} step={10} suffix="km" />
        <NumberInput label="Inclination" value={inclination} onChange={setInclination} min={0} max={180} step={0.1} suffix="deg" />
        <label className="block">
          <span className="text-xs text-[var(--color-ink-soft)]">Ground station</span>
          <input
            value={station}
            onChange={(event) => setStation(event.target.value)}
            maxLength={40}
            className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-2 py-1.5 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
          />
        </label>
        <NumberInput label="Overlapping requests" value={contenders} onChange={setContenders} min={1} max={20} />
        <div className="sm:col-span-2">
          <RunButton onClick={runAll} running={fleet.running || contacts.running} label="Evaluate fleet" />
        </div>
      </Controls>

      {(fleet.error || contacts.error) && <ErrorNote message={fleet.error ?? contacts.error ?? ''} />}

      <SimulationPanel
        title="Fleet sizing"
        description="Planes occupied and the first-order revisit estimate between passes."
        envelope={fleet.data}
      >
        {!fleet.data ? (
          <p className="text-sm text-[var(--color-ink-soft)]">No fleet yet.</p>
        ) : (
          <>
            <Grid columns={3}>
              <Readout label="Satellites" value={String(fleet.data.satellites)} />
              <Readout label="Operational" value={String(fleet.data.operational)} />
              <Readout
                label="Revisit"
                value={
                  fleet.data.revisit_interval_hours == null
                    ? 'no operational satellite'
                    : `${fmt(fleet.data.revisit_interval_hours, 3)} h`
                }
              />
            </Grid>
            <table className="mt-4 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                  <th className="py-2 font-medium">Plane</th>
                  <th className="py-2 font-medium">Alt</th>
                  <th className="hidden py-2 font-medium sm:table-cell">RAAN</th>
                  <th className="py-2 font-medium">Period</th>
                  <th className="py-2 font-medium">Sats</th>
                </tr>
              </thead>
              <tbody>
                {fleet.data.planes.map((plane) => (
                  <tr key={`${plane.raan_deg}-${plane.altitude_km}`} className="border-b border-[var(--color-border)]">
                    <td className="font-tabular py-2 pr-4">{fmt(plane.inclination_deg, 1)}°</td>
                    <td className="font-tabular py-2 pr-4">{fmt(plane.altitude_km, 0)} km</td>
                    <td className="font-tabular hidden py-2 pr-4 sm:table-cell">{fmt(plane.raan_deg, 1)}°</td>
                    <td className="font-tabular py-2 pr-4">{fmt(plane.period_min, 2)} min</td>
                    <td className="font-tabular py-2">{plane.satellites}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </SimulationPanel>

      <SimulationPanel
        title="Ground segment contention"
        description="One antenna per station: overlapping downlinks are refused, not queued."
        envelope={contacts.data}
      >
        {!contacts.data ? (
          <p className="text-sm text-[var(--color-ink-soft)]">No requests yet.</p>
        ) : (
          <>
            <p className="font-tabular text-sm">
              {contacts.data.requested} requested · {contacts.data.granted.length} granted ·{' '}
              {contacts.data.conflicts.length} refused
            </p>
            <ul className="mt-3 space-y-1.5 text-sm">
              {contacts.data.granted.map((grant) => (
                <li key={`${grant.satellite_id}-${grant.start_s}`} className="flex flex-wrap justify-between gap-2">
                  <span>{grant.satellite_id}</span>
                  <span className="font-tabular text-xs text-[var(--color-ink-soft)]">
                    {fmt(grant.start_s, 0)}–{fmt(grant.end_s, 0)} s · {grant.ground_station}
                  </span>
                </li>
              ))}
              {contacts.data.conflicts.map((conflict) => (
                <li
                  key={`${conflict.satellite_id}-${conflict.start_s}`}
                  className="flex flex-wrap justify-between gap-2"
                  style={{ color: 'var(--color-stress)' }}
                >
                  <span>{conflict.satellite_id} refused</span>
                  <span className="font-tabular text-xs">{conflict.reason}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </SimulationPanel>
    </>
  )
}

function PlanningTab() {
  const schedule = useSim<ScheduleResponse>()

  const [tasks, setTasks] = useState(6)
  const [taskLength, setTaskLength] = useState(60)
  const [horizon, setHorizon] = useState(300)
  const [power, setPower] = useState(2)
  const [contactBound, setContactBound] = useState(true)

  const runSchedule = useCallback(() => {
    const count = Math.max(1, Math.min(60, Math.round(tasks)))
    const length = Math.max(1, Math.round(taskLength))
    const windowEnd = Math.max(length, Math.round(horizon) * 1000)
    void schedule.run(() =>
      api.buildSchedule({
        tasks: Array.from({ length: count }, (_, index) => ({
          id: `task-${index + 1}`,
          priority: (index === 0 ? 'critical' : index % 3 === 0 ? 'high' : 'normal') as
            | 'critical'
            | 'high'
            | 'normal',
          earliest_start_s: 0,
          latest_finish_s: windowEnd,
          duration_s: length,
          resource_requirements: { power: 1 },
          requires_contact: contactBound,
        })),
        budgets: [{ name: 'power', capacity: Math.max(0, power), unit: 'kW' }],
        contact_windows: contactBound
          ? [
              { ground_station: 'gs-0', start_s: 0, end_s: length },
              { ground_station: 'gs-0', start_s: windowEnd - length, end_s: windowEnd },
            ]
          : [],
      }),
    )
  }, [schedule, tasks, taskLength, horizon, power, contactBound])

  useEffect(() => {
    runSchedule()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <Controls>
        <NumberInput label="Tasks" value={tasks} onChange={setTasks} min={1} max={60} />
        <NumberInput label="Duration each" value={taskLength} onChange={setTaskLength} min={1} max={600} suffix="s" />
        <NumberInput label="Horizon" value={horizon} onChange={setHorizon} min={1} max={3600} suffix="×1000 s" />
        <NumberInput label="Power capacity" value={power} onChange={setPower} min={0} max={10} suffix="kW" />
        <label className="flex items-end gap-2 pb-2 text-sm text-[var(--color-ink-soft)]">
          <input
            type="checkbox"
            checked={contactBound}
            onChange={(event) => setContactBound(event.target.checked)}
            className="accent-[var(--color-orbit)]"
          />
          All tasks need ground contact
        </label>
        <div className="sm:col-span-2">
          <RunButton onClick={runSchedule} running={schedule.running} label="Build schedule" />
        </div>
      </Controls>

      {schedule.error && <ErrorNote message={schedule.error} />}

      <SimulationPanel
        title="Greedy priority schedule"
        description="Priority-ordered placement over flat resource capacities; refusals say why."
        envelope={schedule.data}
      >
        {!schedule.data ? (
          <p className="text-sm text-[var(--color-ink-soft)]">No schedule yet.</p>
        ) : (
          <>
            <p className="font-tabular text-sm">
              {schedule.data.scheduled.length} placed · {schedule.data.conflicts.length} refused ·{' '}
              horizon {fmt(schedule.data.window_start_s, 0)}–{fmt(schedule.data.window_end_s, 0)} s
            </p>
            <table className="mt-4 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                  <th className="py-2 font-medium">Task</th>
                  <th className="py-2 font-medium">Priority</th>
                  <th className="py-2 font-medium">Start</th>
                  <th className="py-2 font-medium">End</th>
                  <th className="hidden py-2 font-medium sm:table-cell">Contact</th>
                </tr>
              </thead>
              <tbody>
                {schedule.data.scheduled.map((task) => (
                  <tr key={task.id} className="border-b border-[var(--color-border)]">
                    <td className="py-2 pr-4">{task.id}</td>
                    <td className="py-2 pr-4">{task.priority}</td>
                    <td className="font-tabular py-2 pr-4">{fmt(task.start_s, 0)} s</td>
                    <td className="font-tabular py-2 pr-4">{fmt(task.end_s, 0)} s</td>
                    <td className="font-tabular hidden py-2 sm:table-cell">
                      {task.requires_contact ? 'yes' : 'no'}
                    </td>
                  </tr>
                ))}
                {schedule.data.conflicts.map((task) => (
                  <tr key={task.id} className="border-b border-[var(--color-border)]">
                    <td className="py-2 pr-4">{task.id}</td>
                    <td className="py-2 pr-4">{task.priority}</td>
                    <td className="py-2" style={{ color: 'var(--color-stress)' }} colSpan={3}>
                      {task.reason}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </SimulationPanel>
    </>
  )
}

const ENVIRONMENTS = ['earth', 'orbital', 'lunar', 'mars', 'deep_space']

function AutonomyTab() {
  const decision = useSim<StackDecisionResponse>()
  const environments = useSim<EnvironmentListResponse>()
  const delay = useSim<CommsDelayResponse>()

  const [environment, setEnvironment] = useState('lunar')
  const [battery, setBattery] = useState(72)
  const [autonomy, setAutonomy] = useState(3)
  const [powerAvailable, setPowerAvailable] = useState(120)
  const [powerDemand, setPowerDemand] = useState(80)
  const [temperature, setTemperature] = useState(-40)
  const [target, setTarget] = useState<CommsTarget>('mars')

  const runAll = useCallback(() => {
    void decision.run(() =>
      api.decideStack({
        environment,
        target_body: environment,
        autonomy_level: Math.min(5, Math.max(1, Math.round(autonomy))),
        battery_percent: Math.min(100, Math.max(0, battery)),
        power_available_w: Math.max(0, powerAvailable),
        power_demand_w: Math.max(0, powerDemand),
        temperature_c: temperature,
        in_contact: true,
      }),
    )
    void delay.run(() => api.commsDelay(target))
  }, [decision, delay, environment, autonomy, battery, powerAvailable, powerDemand, temperature, target])

  useEffect(() => {
    runAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void environments.run(() => api.listEnvironments())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <Controls>
        <Choice
          label="Environment"
          value={environment}
          onChange={setEnvironment}
          options={ENVIRONMENTS.map((name) => ({ value: name, label: name }))}
        />
        <NumberInput label="Battery" value={battery} onChange={setBattery} min={0} max={100} suffix="%" />
        <NumberInput label="Autonomy level" value={autonomy} onChange={setAutonomy} min={1} max={5} />
        <NumberInput label="Power available" value={powerAvailable} onChange={setPowerAvailable} min={0} max={5000} suffix="W" />
        <NumberInput label="Power demanded" value={powerDemand} onChange={setPowerDemand} min={0} max={5000} suffix="W" />
        <NumberInput label="Temperature" value={temperature} onChange={setTemperature} min={-120} max={60} step={1} suffix="°C" />
        <Choice
          label="Comms target"
          value={target}
          onChange={(value) => setTarget(value as CommsTarget)}
          options={COMMS_TARGETS.map((name) => ({ value: name, label: name }))}
        />
        <div className="sm:col-span-2">
          <RunButton onClick={runAll} running={decision.running} label="Run one decision cycle" />
        </div>
      </Controls>

      {(decision.error || delay.error) && <ErrorNote message={decision.error ?? delay.error ?? ''} />}

      <SimulationPanel
        title="Decision cycle"
        description="Seven layers propose; mission control filters by the autonomy budget; a fail-safe trips on critical state."
        envelope={decision.data}
      >
        {!decision.data ? (
          <p className="text-sm text-[var(--color-ink-soft)]">No cycle yet.</p>
        ) : (
          <>
            {decision.data.safe_mode_active && (
              <p
                className="mb-4 rounded-sm px-3 py-2 text-sm font-medium"
                style={{ backgroundColor: 'var(--color-critical-soft)', color: 'var(--color-critical)' }}
              >
                Safe mode tripped this cycle: {decision.data.warnings.join('; ') || 'critical state'}
              </p>
            )}
            <p className="font-tabular text-xs text-[var(--color-ink-soft)]">
              layers: {decision.data.layers_evaluated.join(' → ')}
            </p>
            <ActionList title="Approved" actions={decision.data.approved} color="var(--color-healthy)" />
            <ActionList
              title="Awaiting authorization"
              actions={decision.data.pending_authorization}
              color="var(--color-orbit)"
            />
            <ActionList title="Rejected" actions={decision.data.rejected} color="var(--color-stress)" />
          </>
        )}
      </SimulationPanel>

      <div className="grid gap-8 lg:grid-cols-2">
        <SimulationPanel
          title="Light-time and autonomy"
          description="One-way delay drives how much autonomy operations must carry."
          envelope={delay.data}
        >
          {!delay.data ? (
            <p className="text-sm text-[var(--color-ink-soft)]">No data.</p>
          ) : (
            <Grid columns={3}>
              <Readout label="One-way" value={`${fmt(delay.data.owlt_s, 1)} s`} />
              <Readout label="Round trip" value={`${fmt(delay.data.rtt_s, 1)} s`} />
              <Readout label="Autonomy level" value={String(delay.data.autonomy_level)} />
              <Readout label="Real-time control" value={delay.data.real_time ? 'yes' : 'no'} />
              <Readout label="Contact interval" value={`${fmt(delay.data.recommended_contact_interval_s, 0)} s`} />
              <Readout label="Max autonomous ops" value={`${fmt(delay.data.max_autonomous_operations_s, 0)} s`} />
            </Grid>
          )}
        </SimulationPanel>

        <SimulationPanel
          title="Environment constants"
          description="The planning values the simulators assume about each body."
          envelope={environments.data}
        >
          {!environments.data ? (
            <p className="text-sm text-[var(--color-ink-soft)]">No data.</p>
          ) : (
            <table className="mt-1 w-full text-left text-sm">
              <tbody>
                {environments.data.environments.map((env) => (
                  <tr key={env.name} className="border-b border-[var(--color-border)]">
                    <td className="py-2 pr-4 font-medium">{env.name}</td>
                    <td className="font-tabular py-2 pr-4">{fmt(env.gravity_ms2, 2)} m/s²</td>
                    <td className="font-tabular hidden py-2 pr-4 sm:table-cell">
                      {fmt(env.solar_flux_wm2, 0)} W/m²
                    </td>
                    <td className="font-tabular py-2 text-[var(--color-ink-soft)]">
                      {fmt(env.mean_temperature_c, 1)} °C
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SimulationPanel>
      </div>
    </>
  )
}

const COMMS_TARGETS: CommsTarget[] = [
  'earth_leo',
  'moon',
  'mars',
  'jupiter',
  'saturn',
  'asteroid',
  'deep_space',
]

function ActionList({
  title,
  actions,
  color,
}: {
  title: string
  actions: StackDecisionResponse['approved']
  color: string
}) {
  if (actions.length === 0) return null
  return (
    <div className="mt-4">
      <p className="text-xs font-semibold uppercase tracking-wide" style={{ color }}>
        {title}
      </p>
      <ul className="mt-1.5 space-y-1.5 text-sm">
        {actions.map((action) => (
          <li key={`${action.layer}-${action.target}-${action.description}`} className="flex gap-2">
            <span className="font-tabular shrink-0 text-xs text-[var(--color-ink-soft)]">
              {action.layer} → {action.target}
            </span>
            <span>{action.description}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const PROCESSES: ExtractionProcess[] = [
  'water_ice',
  'oxygen_regolith',
  'metals',
  'construction_material',
  'generic',
]

function ResourcesTab() {
  const technologies = useSim<TechnologyListResponse>()
  const extraction = useSim<ExtractionResponse>()
  const economics = useSim<EconomicsResponse>()
  const roadmap = useSim<RoadmapResponse>()

  const [body, setBody] = useState('')
  const [minTrl, setMinTrl] = useState(1)
  const [process, setProcess] = useState<ExtractionProcess>('water_ice')
  const [hours, setHours] = useState(24)
  const [feedstock, setFeedstock] = useState(1000)
  const [power, setPower] = useState(0)
  const [resource, setResource] = useState('water')
  const [mass, setMass] = useState(250)
  const [destination, setDestination] = useState('lunar')

  const runAll = useCallback(() => {
    void technologies.run(() =>
      api.listTechnologies({
        target_body: body || undefined,
        min_trl: Math.min(9, Math.max(1, Math.round(minTrl))),
      }),
    )
    void extraction.run(() =>
      api.simulateExtraction({
        process,
        hours: Math.max(0.1, hours),
        feedstock_kg: Math.max(0, feedstock),
        power_w: power > 0 ? power : undefined,
      }),
    )
    void economics.run(() =>
      api.deliveryEconomics(resource, {
        mass_kg: Math.max(1, mass),
        destination,
      }),
    )
  }, [technologies, extraction, economics, body, minTrl, process, hours, feedstock, power, resource, mass, destination])

  useEffect(() => {
    runAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <Controls>
        <Choice
          label="Target body"
          value={body}
          onChange={setBody}
          options={[
            { value: '', label: 'All bodies' },
            { value: 'lunar', label: 'lunar' },
            { value: 'mars', label: 'mars' },
            { value: 'asteroid', label: 'asteroid' },
          ]}
        />
        <NumberInput label="Minimum TRL" value={minTrl} onChange={setMinTrl} min={1} max={9} />
        <Choice
          label="Extraction process"
          value={process}
          onChange={(value) => setProcess(value as ExtractionProcess)}
          options={PROCESSES.map((name) => ({ value: name, label: name }))}
        />
        <NumberInput label="Operating time" value={hours} onChange={setHours} min={0.1} max={8760} step={1} suffix="h" />
        <NumberInput label="Feedstock" value={feedstock} onChange={setFeedstock} min={0} max={1000000} step={50} suffix="kg" />
        <NumberInput label="Power override" value={power} onChange={setPower} min={0} max={100000} step={10} suffix="W (0 = default)" />
        <Choice
          label="Resource"
          value={resource}
          onChange={setResource}
          options={['water', 'oxygen', 'metals', 'propellant', 'construction_material'].map((name) => ({
            value: name,
            label: name,
          }))}
        />
        <NumberInput label="Mass to deliver" value={mass} onChange={setMass} min={1} max={1000000} step={10} suffix="kg" />
        <Choice
          label="Destination"
          value={destination}
          onChange={setDestination}
          options={[
            { value: 'lunar', label: 'lunar' },
            { value: 'mars', label: 'mars' },
          ]}
        />
        <div className="flex flex-wrap items-end gap-3 sm:col-span-2">
          <RunButton onClick={runAll} running={technologies.running || extraction.running} label="Run models" />
          <RunButton
            onClick={() => void roadmap.run(() => api.programRoadmap())}
            running={roadmap.running}
            label="Load roadmap"
          />
        </div>
      </Controls>

      {(technologies.error || extraction.error || economics.error || roadmap.error) && (
        <ErrorNote
          message={technologies.error ?? extraction.error ?? economics.error ?? roadmap.error ?? ''}
        />
      )}

      <SimulationPanel
        title="Technology registry"
        description="TRL-grounded ISRU technologies with hand-entered mass, power and rate."
        envelope={technologies.data}
      >
        {!technologies.data ? (
          <p className="text-sm text-[var(--color-ink-soft)]">No data.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                <th className="py-2 font-medium">Technology</th>
                <th className="py-2 font-medium">TRL</th>
                <th className="hidden py-2 font-medium md:table-cell">Power</th>
                <th className="py-2 font-medium">kg/day</th>
                <th className="hidden py-2 font-medium sm:table-cell">Risk</th>
              </tr>
            </thead>
            <tbody>
              {technologies.data.technologies.map((tech) => (
                <tr key={tech.id} className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-4">
                    {tech.name}
                    <span className="block text-xs text-[var(--color-ink-soft)]">
                      {tech.target_body} · {tech.resource_type} · {tech.readiness}
                    </span>
                  </td>
                  <td className="font-tabular py-2 pr-4">{tech.trl}</td>
                  <td className="font-tabular hidden py-2 pr-4 md:table-cell">{fmt(tech.power_w, 0)} W</td>
                  <td className="font-tabular py-2 pr-4">{fmt(tech.production_kg_per_day, 2)}</td>
                  <td className="font-tabular hidden py-2 text-[var(--color-ink-soft)] sm:table-cell">
                    {fmt(tech.risk_overall, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SimulationPanel>

      <div className="grid gap-8 lg:grid-cols-2">
        <SimulationPanel
          title="Extraction run"
          description="Power in, resource out, against one simplified energy-to-mass constant."
          envelope={extraction.data}
        >
          {!extraction.data ? (
            <p className="text-sm text-[var(--color-ink-soft)]">No run.</p>
          ) : (
            <>
              <Grid columns={2}>
                <Readout label="Produced" value={`${fmt(extraction.data.mass_produced_kg, 4)} kg`} />
                <Readout label="Waste" value={`${fmt(extraction.data.mass_waste_kg, 4)} kg`} />
                <Readout label="Energy" value={`${fmt(extraction.data.energy_used_wh, 1)} Wh`} />
                <Readout label="Yield fraction" value={fmt(extraction.data.yield_fraction, 4)} />
                <Readout
                  label="Specific energy"
                  value={
                    extraction.data.specific_energy_kwh_per_kg == null
                      ? 'n/a (nothing produced)'
                      : `${fmt(extraction.data.specific_energy_kwh_per_kg, 4)} kWh/kg`
                  }
                />
                <Readout label="Plant status" value={extraction.data.status} />
              </Grid>
              {extraction.data.mass_produced_kg === 0 && (
                <p className="mt-3 text-sm" style={{ color: 'var(--color-stress)' }}>
                  Nothing produced. For the sinterer that means no feedstock was supplied.
                </p>
              )}
            </>
          )}
        </SimulationPanel>

        <SimulationPanel
          title="Delivery economics"
          description="One cost literal per kilogram per destination. An argument for more study, not a business case."
          envelope={economics.data}
        >
          {!economics.data ? (
            <p className="text-sm text-[var(--color-ink-soft)]">No data.</p>
          ) : (
            <>
              <Grid columns={2}>
                <Readout label="Launch from Earth" value={`$${Math.round(economics.data.earth_launch_cost).toLocaleString()}`} />
                <Readout label="Produce in situ" value={`$${Math.round(economics.data.in_situ_cost).toLocaleString()}`} />
                <Readout label="Saving" value={`$${Math.round(economics.data.savings).toLocaleString()}`} />
                <Readout label="Saving share" value={`${fmt(economics.data.savings_percent, 1)}%`} />
              </Grid>
              <p className="font-tabular mt-4 text-xs text-[var(--color-ink-soft)]">
                {economics.data.mass_kg} kg of {economics.data.resource_type} to{' '}
                {economics.data.destination} · excludes development, launch vehicle, ops and insurance
              </p>
            </>
          )}
        </SimulationPanel>
      </div>

      <SimulationPanel title="Programme roadmap" description="Eight phases of hand-declared milestones." envelope={roadmap.data}>
        {!roadmap.data ? (
          <p className="text-sm text-[var(--color-ink-soft)]">
            Load the roadmap to see the phase table and total cost.
          </p>
        ) : (
          <>
            <Grid columns={4}>
              <Readout label="Milestones" value={String(roadmap.data.total_milestones)} />
              <Readout label="Critical path" value={String(roadmap.data.critical_path_milestones)} />
              <Readout
                label="Cost"
                value={`$${(roadmap.data.total_cost_usd / 1e9).toFixed(2)}B`}
              />
              <Readout label="Duration" value={`${fmt(roadmap.data.total_duration_years, 0)} yr`} />
            </Grid>
            <table className="mt-4 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                  <th className="py-2 font-medium">Phase</th>
                  <th className="py-2 font-medium">Milestones</th>
                  <th className="hidden py-2 font-medium sm:table-cell">Cost</th>
                  <th className="py-2 font-medium">Years</th>
                </tr>
              </thead>
              <tbody>
                {roadmap.data.phases.map((phase) => (
                  <tr key={phase.phase_number} className="border-b border-[var(--color-border)]">
                    <td className="py-2 pr-4">
                      {phase.phase}
                      <span className="font-tabular block text-xs text-[var(--color-ink-soft)]">
                        {fmt(phase.start_year, 0)}–{fmt(phase.end_year, 0)}
                      </span>
                    </td>
                    <td className="font-tabular py-2 pr-4">
                      {phase.milestone_count} ({phase.critical_milestones} critical)
                    </td>
                    <td className="font-tabular hidden py-2 pr-4 sm:table-cell">
                      ${(phase.total_cost_usd / 1e6).toFixed(1)}M
                    </td>
                    <td className="font-tabular py-2">{fmt(phase.duration_years, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </SimulationPanel>

      <p className="text-xs text-[var(--color-ink-soft)]">
        Nothing on this page is flight-qualified, priced or measured. <ProvenanceBadge provenance="simulated" />
      </p>
    </>
  )
}
