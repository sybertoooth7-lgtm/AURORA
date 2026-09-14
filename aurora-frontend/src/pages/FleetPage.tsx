import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../lib/api'
import type { FlightSummary } from '../lib/types'

const DEFAULT_LATITUDE = -1.2921
const DEFAULT_LONGITUDE = 36.8219

function formatDate(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function healthColor(score: number): string {
  if (score >= 0.8) return '#4F7942'
  if (score >= 0.5) return '#B8860B'
  return '#8C2F1B'
}

export function FleetPage() {
  const [flights, setFlights] = useState<FlightSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [simulating, setSimulating] = useState(false)
  const [simError, setSimError] = useState<string | null>(null)
  const [lat, setLat] = useState(String(DEFAULT_LATITUDE))
  const [lon, setLon] = useState(String(DEFAULT_LONGITUDE))
  const [radius, setRadius] = useState('5')
  const [frames, setFrames] = useState('20')

  const refresh = useCallback(() => {
    api
      .listFlights()
      .then((data) => {
        setFlights(data.flights)
        setLoadError(null)
      })
      .catch((err) => {
        setLoadError(err instanceof ApiError ? err.message : 'Could not load the fleet.')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 15000)
    return () => clearInterval(timer)
  }, [refresh])

  async function handleSimulate(event: FormEvent) {
    event.preventDefault()
    setSimError(null)
    const parsedLat = Number(lat)
    const parsedLon = Number(lon)
    const parsedRadius = Number(radius)
    const parsedFrames = Number(frames)
    if (Number.isNaN(parsedLat) || parsedLat < -90 || parsedLat > 90) {
      setSimError('Latitude must be a number between -90 and 90.')
      return
    }
    if (Number.isNaN(parsedLon) || parsedLon < -180 || parsedLon > 180) {
      setSimError('Longitude must be a number between -180 and 180.')
      return
    }
    if (Number.isNaN(parsedRadius) || parsedRadius <= 0 || parsedRadius > 500) {
      setSimError('Radius must be a number between 0 and 500 km.')
      return
    }
    if (Number.isNaN(parsedFrames) || parsedFrames < 5 || parsedFrames > 120) {
      setSimError('Frame count must be between 5 and 120.')
      return
    }
    setSimulating(true)
    try {
      await api.simulateFlight({
        latitude: parsedLat,
        longitude: parsedLon,
        radius_km: parsedRadius,
        num_frames: parsedFrames,
      })
      await refresh()
    } catch (err) {
      setSimError(err instanceof ApiError ? err.message : 'Could not spawn the simulated flight.')
    } finally {
      setSimulating(false)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header>
        <h1 className="font-[var(--font-display)] text-2xl font-semibold">Operations fleet</h1>
        <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
          Telemetry from the field-robot fleet updated every few seconds. Simulated flights drive
          the same dashboards as live ones and are labelled honestly.
        </p>
      </header>

      <section className="mt-8 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
          Spawn a simulated flight
        </h2>
        <form onSubmit={handleSimulate} className="mt-4 grid grid-cols-2 gap-4 md:grid-cols-4">
          <label className="block text-sm font-medium">
            Latitude
            <input
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              inputMode="decimal"
              required
              className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </label>
          <label className="block text-sm font-medium">
            Longitude
            <input
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              inputMode="decimal"
              required
              className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </label>
          <label className="block text-sm font-medium">
            Radius (km)
            <input
              value={radius}
              onChange={(e) => setRadius(e.target.value)}
              inputMode="decimal"
              required
              className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </label>
          <label className="block text-sm font-medium">
            Frames
            <input
              value={frames}
              onChange={(e) => setFrames(e.target.value)}
              inputMode="numeric"
              required
              className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </label>
          <div className="col-span-2 md:col-span-4">
            {simError && <p className="text-sm text-[var(--color-critical)]">{simError}</p>}
            <button
              type="submit"
              disabled={simulating}
              className="mt-2 rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {simulating ? 'Spawning…' : 'Spawn simulated flight'}
            </button>
          </div>
        </form>
      </section>

      <section className="mt-10">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
          Flights
        </h2>
        {loading ? (
          <p className="mt-4 text-sm text-[var(--color-ink-soft)]">Loading fleet…</p>
        ) : loadError ? (
          <p className="mt-4 text-sm text-[var(--color-stress)]">{loadError}</p>
        ) : flights.length === 0 ? (
          <div className="mt-4 rounded-sm border border-[var(--color-border)] px-6 py-10 text-center">
            <p className="font-[var(--font-display)] text-lg font-semibold">No flights in the process yet</p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-[var(--color-ink-soft)]">
              Spawn a simulated flight above to see the fleet dashboard, or have a robot start
              publishing telemetry to the bridge.
            </p>
          </div>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                <th className="py-2 font-medium">Flight</th>
                <th className="py-2 font-medium">Started</th>
                <th className="py-2 font-medium">Frames</th>
                <th className="py-2 font-medium">Health</th>
                <th className="hidden py-2 font-medium sm:table-cell">Status</th>
                <th className="hidden py-2 font-medium sm:table-cell">Faults</th>
              </tr>
            </thead>
            <tbody>
              {flights.map((flight) => {
                const health = flight.flight_health
                return (
                  <tr key={flight.flight_id} className="border-b border-[var(--color-border)]">
                    <td className="py-2 pr-4">
                      <Link
                        to={`/app/fleet/${flight.flight_id}`}
                        className="font-mono text-[var(--color-ink)] underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-orbit)]"
                      >
                        {flight.flight_id}
                      </Link>
                    </td>
                    <td className="font-tabular py-2 pr-4 text-[var(--color-ink-soft)]">
                      {formatDate(flight.started_at)}
                    </td>
                    <td className="font-tabular py-2 pr-4">{flight.telemetry_count}</td>
                    <td className="py-2 pr-4">
                      <span className="font-tabular font-semibold" style={{ color: healthColor(health.health_score) }}>
                        {(health.health_score * 100).toFixed(0)}
                      </span>
                      <span className="text-[var(--color-ink-soft)]">%</span>
                    </td>
                    <td className="hidden py-2 pr-4 text-[var(--color-ink-soft)] sm:table-cell">
                      {health.status}
                    </td>
                    <td className="font-tabular hidden py-2 text-[var(--color-ink-soft)] sm:table-cell">
                      {health.fault_count}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}