import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, api } from '../lib/api'
import type { FlightHealth, RoboticsInspectResponse, TelemetryFrame } from '../lib/types'

const CHART_WIDTH = 640
const CHART_HEIGHT = 140

function Sparkline({
  values,
  color,
  unit,
}: {
  values: Array<number | null>
  color: string
  unit: string
}) {
  const points = useMemo(() => {
    const present = values.filter((value): value is number => value != null)
    if (present.length === 0) return null
    const bounds = { min: Math.min(...present), max: Math.max(...present) }
    const span = bounds.max - bounds.min || 1
    const pad = 6
    return values
      .map((value, i) => {
        if (value == null) return null
        const x = pad + (i / Math.max(values.length - 1, 1)) * (CHART_WIDTH - pad * 2)
        const y = pad + (1 - (value - bounds.min) / span) * (CHART_HEIGHT - pad * 2)
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .filter((point): point is string => point != null)
      .join(' ')
  }, [values])

  return (
    <svg
      viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
      preserveAspectRatio="none"
      className="font-tabular h-40 w-full"
      role="img"
    >
      {points && (
        <polyline points={points} fill="none" stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke" />
      )}
      <text x={8} y={CHART_HEIGHT - 6} fill="currentColor" opacity={0.55} style={{ fontSize: 11 }}>
        {unit}
      </text>
    </svg>
  )
}

function ChartCard({
  title,
  values,
  color,
  unit,
}: {
  title: string
  values: Array<number | null>
  color: string
  unit: string
}) {
  return (
    <div className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 pb-3 pt-4">
      <div className="flex items-baseline justify-between">
        <p className="text-sm font-medium">{title}</p>
        <p className="font-tabular text-sm text-[var(--color-ink-soft)]">
          {values[values.length - 1]?.toFixed(1) ?? '—'} {unit}
        </p>
      </div>
      <Sparkline values={values} color={color} unit={unit} />
    </div>
  )
}

export function FlightDetailPage() {
  const { flightId } = useParams<{ flightId: string }>()
  const [frames, setFrames] = useState<TelemetryFrame[]>([])
  const [health, setHealth] = useState<FlightHealth | null>(null)
  const [startedAt, setStartedAt] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [inspectLat, setInspectLat] = useState('-1.2921')
  const [inspectLon, setInspectLon] = useState('36.8219')
  const [inspectRadius, setInspectRadius] = useState('5')
  const [inspecting, setInspecting] = useState(false)
  const [inspectError, setInspectError] = useState<string | null>(null)
  const [inspectResult, setInspectResult] = useState<RoboticsInspectResponse | null>(null)

  const refresh = useCallback(() => {
    if (!flightId) return
    api
      .getFlightTelemetry(flightId, 200)
      .then((data) => {
        setFrames(data)
        setLoadError(null)
      })
      .catch((err) => {
        setLoadError(err instanceof ApiError ? err.message : 'Could not load telemetry.')
      })
    api
      .getFlight(flightId)
      .then((data) => {
        setHealth(data.flight_health)
        setStartedAt(data.started_at)
      })
      .catch(() => {})
  }, [flightId])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 5000)
    return () => clearInterval(timer)
  }, [refresh])

  const isSimulated = useMemo(() => {
    if (frames.some((frame) => frame.is_simulated)) return true
    return flightId?.startsWith('sim-') ?? false
  }, [frames, flightId])

  const battery = frames.map((frame) => frame.battery_percent)
  const altitude = frames.map((frame) => frame.altitude_m)
  const motorTemp = frames.map((frame) => frame.motor_temp_c)
  const gpsAccuracy = frames.map((frame) => frame.gps_accuracy_m)
  const faults = useMemo(() => {
    const seen = new Set<string>()
    const ordered: Array<{ frame: string; label: string }> = []
    for (let i = frames.length - 1; i >= 0; i -= 1) {
      for (const label of frames[i].faults ?? []) {
        if (!seen.has(label)) {
          seen.add(label)
          ordered.push({ frame: frames[i].sequence?.toString() ?? String(i), label })
        }
      }
    }
    return ordered
  }, [frames])

  async function handleInspect(event: FormEvent) {
    event.preventDefault()
    if (!flightId) return
    setInspectError(null)
    setInspectResult(null)
    const parsedLat = Number(inspectLat)
    const parsedLon = Number(inspectLon)
    const parsedRadius = Number(inspectRadius)
    if (Number.isNaN(parsedLat) || parsedLat < -90 || parsedLat > 90) {
      setInspectError('Latitude must be a number between -90 and 90.')
      return
    }
    if (Number.isNaN(parsedLon) || parsedLon < -180 || parsedLon > 180) {
      setInspectError('Longitude must be a number between -180 and 180.')
      return
    }
    if (Number.isNaN(parsedRadius) || parsedRadius <= 0 || parsedRadius > 500) {
      setInspectError('Radius must be a number between 0 and 500 km.')
      return
    }
    setInspecting(true)
    try {
      const result = await api.inspectFlightArea({
        latitude: parsedLat,
        longitude: parsedLon,
        radius_km: parsedRadius,
        flight_id: flightId,
      })
      setInspectResult(result)
    } catch (err) {
      setInspectError(err instanceof ApiError ? err.message : 'Could not run the inspection.')
    } finally {
      setInspecting(false)
    }
  }

  if (!flightId) return null

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <Link to="/app/fleet" className="text-sm text-[var(--color-orbit)] underline underline-offset-2">
        ← All flights
      </Link>

      <header className="mt-2 flex flex-wrap items-baseline gap-3">
        <h1 className="font-mono font-[var(--font-display)] text-2xl font-semibold">{flightId}</h1>
        {isSimulated && (
          <span className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-2 py-0.5 text-xs font-medium text-[var(--color-ink-soft)]">
            Simulated
          </span>
        )}
        {startedAt && (
          <p className="text-sm text-[var(--color-ink-soft)]">
            Started {new Date(startedAt).toLocaleString()}
          </p>
        )}
      </header>

      {loadError ? (
        <p className="mt-8 text-sm text-[var(--color-stress)]">{loadError}</p>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-3 gap-4 sm:grid-cols-5">
            <Kpi label="Health" value={health ? `${(health.health_score * 100).toFixed(0)}%` : '—'} detail={health?.status ?? ''} />
            <Kpi label="Frames" value={String(frames.length)} detail="last 200 shown" />
            <Kpi label="Faults" value={String(health?.fault_count ?? 0)} detail="distinct telemetry faults" />
            <Kpi label="Min battery" value={health?.battery_min != null ? `${health.battery_min.toFixed(0)}%` : '—'} detail="during flight" />
            <Kpi
              label="Latest battery"
              value={battery[battery.length - 1]?.toFixed(0) ?? '—'}
              detail={isSimulated ? 'simulated stream' : 'live stream'}
            />
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <ChartCard title="Battery" values={battery} color="#2E86AB" unit="%" />
            <ChartCard title="Altitude" values={altitude} color="#4F7942" unit="m" />
            <ChartCard title="Motor temperature" values={motorTemp} color="#8C2F1B" unit="°C" />
            <ChartCard title="GPS accuracy" values={gpsAccuracy} color="#B8860B" unit="m" />
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <section className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-4">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
                Fault log
              </h2>
              {faults.length === 0 ? (
                <p className="mt-3 text-sm text-[var(--color-ink-soft)]">No faults recorded.</p>
              ) : (
                <ul className="mt-3 space-y-1">
                  {faults.map((fault) => (
                    <li key={fault.label} className="flex items-baseline justify-between text-sm">
                      <span className="text-[var(--color-critical)]">{fault.label}</span>
                      <span className="font-tabular text-xs text-[var(--color-ink-soft)]">frame {fault.frame}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-4">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
                Post-flight satellite inspection
              </h2>
              <form onSubmit={handleInspect} className="mt-3 space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <label className="block text-sm font-medium">
                    Latitude
                    <input
                      value={inspectLat}
                      onChange={(e) => setInspectLat(e.target.value)}
                      inputMode="decimal"
                      required
                      className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
                    />
                  </label>
                  <label className="block text-sm font-medium">
                    Longitude
                    <input
                      value={inspectLon}
                      onChange={(e) => setInspectLon(e.target.value)}
                      inputMode="decimal"
                      required
                      className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
                    />
                  </label>
                  <label className="block text-sm font-medium">
                    Radius (km)
                    <input
                      value={inspectRadius}
                      onChange={(e) => setInspectRadius(e.target.value)}
                      inputMode="decimal"
                      required
                      className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
                    />
                  </label>
                </div>
                {inspectError && <p className="text-sm text-[var(--color-critical)]">{inspectError}</p>}
                <button
                  type="submit"
                  disabled={inspecting}
                  className="rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
                >
                  {inspecting ? 'Inspecting…' : 'Run satellite inspection'}
                </button>
              </form>

              {inspectResult && (
                <div className="mt-4 border-t border-[var(--color-border)] pt-3">
                  <p className="font-tabular text-sm text-[var(--color-ink-soft)]">
                    Damage proxy{' '}
                    <span className="font-semibold text-[var(--color-ink)]">
                      {(inspectResult.vsatellite_damage_proxy ?? 0).toFixed(2)}
                    </span>{' '}
                    · severity{' '}
                    <span className="font-semibold text-[var(--color-ink)]">
                      {inspectResult.result.severity.toFixed(2)}
                    </span>
                  </p>
                  <ul className="mt-2 space-y-1">
                    {inspectResult.combined_report.map((line, i) => (
                      <li key={i} className="text-sm text-[var(--color-ink-soft)]">
                        {line}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-xs text-[var(--color-ink-soft)]">
                    Full report linked from the{' '}
                    <Link to={`/app/areas/${inspectResult.analysis_id}`} className="text-[var(--color-orbit)] underline underline-offset-2">
                      area page
                    </Link>
                    .
                  </p>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}

function Kpi({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-3">
      <p className="text-xs text-[var(--color-ink-soft)]">{label}</p>
      <p className="font-tabular mt-1 truncate text-lg font-semibold">{value}</p>
      <p className="mt-0.5 truncate text-xs text-[var(--color-ink-soft)]">{detail}</p>
    </div>
  )
}