import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardContext } from '../components/Layout'
import { api } from '../lib/api'
import {
  ANALYSIS_TYPE_LABELS,
  monitoringCadenceLabel,
  type Alert,
  type Analysis,
} from '../lib/types'

const STATUS_LABELS: Record<Analysis['status'], { label: string; color: string }> = {
  pending: { label: 'Queued', color: 'var(--color-ink-soft)' },
  processing: { label: 'Processing', color: 'var(--color-orbit)' },
  completed: { label: 'Completed', color: '#4F7942' },
  failed: { label: 'Failed', color: '#8C2F1B' },
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function DashboardPage() {
  const { areas } = useDashboardContext()
  const [alerts, setAlerts] = useState<Alert[]>([])

  useEffect(() => {
    let cancelled = false
    api
      .listAlerts()
      .then((data) => {
        if (!cancelled) setAlerts(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  const monitored = areas.filter((area) => area.monitor_interval_minutes != null)
  const inFlight = areas.filter(
    (area) => area.status === 'pending' || area.status === 'processing',
  )
  const openAlerts = alerts.filter((alert) => alert.acknowledged_at == null)
  const nextChecks = monitored
    .map((area) => area.next_check_at)
    .filter((value): value is string => value != null)
    .map((value) => new Date(value).getTime())
  const nextCheckAt = nextChecks.length > 0 ? new Date(Math.min(...nextChecks)) : null

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex items-end justify-between">
        <div>
          <h1 className="font-[var(--font-display)] text-2xl font-semibold">Overview</h1>
          <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
            Live space-intelligence coverage across your monitored areas.
          </p>
        </div>
        <Link
          to="/app/areas/new"
          className="rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90"
        >
          + New area
        </Link>
      </header>

      <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Kpi label="Areas tracked" value={String(areas.length)} detail={`${monitored.length} monitored`} />
        <Kpi label="Checks in flight" value={String(inFlight.length)} detail="queued or processing" />
        <Kpi label="Open alerts" value={String(openAlerts.length)} detail="not yet acknowledged" />
        <Kpi
          label="Next scheduled check"
          value={nextCheckAt ? formatDate(nextCheckAt.toISOString()) : '—'}
          detail="soonest monitored cadence"
        />
      </div>

      <section className="mt-10">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
          Areas
        </h2>

        {areas.length === 0 ? (
          <div className="mt-4 rounded-sm border border-[var(--color-border)] px-6 py-10 text-center">
            <p className="font-[var(--font-display)] text-lg font-semibold">No areas monitored yet</p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-[var(--color-ink-soft)]">
              Add a location and AURORA will check the latest cloud-free satellite pass over it
              for vegetation stress, land change, and more — optionally on a repeating schedule.
            </p>
            <Link
              to="/app/areas/new"
              className="mt-6 inline-block rounded-sm border border-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-orbit)] transition-colors hover:bg-[var(--color-orbit)] hover:text-[var(--color-paper)]"
            >
              Add your first area
            </Link>
          </div>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                <th className="py-2 font-medium">Area</th>
                <th className="hidden py-2 font-medium md:table-cell">Checks for</th>
                <th className="py-2 font-medium">Status</th>
                <th className="hidden py-2 font-medium sm:table-cell">Monitoring</th>
                <th className="hidden py-2 font-medium lg:table-cell">Last check</th>
                <th className="py-2 font-medium">Next check</th>
              </tr>
            </thead>
            <tbody>
              {areas.map((area) => {
                const status = STATUS_LABELS[area.status]
                return (
                  <tr key={area.id} className="border-b border-[var(--color-border)]">
                    <td className="py-2 pr-4">
                      <Link
                        to={`/app/areas/${area.id}`}
                        className="font-medium text-[var(--color-ink)] underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-orbit)]"
                      >
                        {area.description || ANALYSIS_TYPE_LABELS[area.analysis_type]}
                      </Link>
                      <span className="font-tabular mt-0.5 block text-xs text-[var(--color-ink-soft)]">
                        {area.latitude.toFixed(3)}, {area.longitude.toFixed(3)} &middot; {area.radius_km}km
                      </span>
                    </td>
                    <td className="hidden py-2 pr-4 text-[var(--color-ink-soft)] md:table-cell">
                      {ANALYSIS_TYPE_LABELS[area.analysis_type]}
                    </td>
                    <td className="py-2 pr-4">
                      <span style={{ color: status.color }}>
                        {status.label}
                      </span>
                    </td>
                    <td className="hidden py-2 pr-4 text-[var(--color-ink-soft)] sm:table-cell">
                      {monitoringCadenceLabel(area.monitor_interval_minutes)}
                    </td>
                    <td className="font-tabular hidden py-2 pr-4 text-[var(--color-ink-soft)] lg:table-cell">
                      {formatDate(area.completed_at)}
                    </td>
                    <td className="font-tabular py-2 text-[var(--color-ink-soft)]">
                      {formatDate(area.next_check_at)}
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

function Kpi({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-3">
      <p className="text-xs text-[var(--color-ink-soft)]">{label}</p>
      <p className="font-tabular mt-1 truncate text-lg font-semibold">{value}</p>
      <p className="mt-0.5 text-xs text-[var(--color-ink-soft)]">{detail}</p>
    </div>
  )
}