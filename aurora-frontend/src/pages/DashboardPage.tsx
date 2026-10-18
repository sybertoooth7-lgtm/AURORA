import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useDashboardContext } from '../components/Layout'
import { api } from '../lib/api'
import {
  ANALYSIS_TYPE_LABELS,
  monitoringCadenceLabel,
  type Analysis,
  type AnalysisListQuery,
  type AnalysisStatus,
  type AnalysisSummaryResponse,
} from '../lib/types'

const STATUS_LABELS: Record<AnalysisStatus, { label: string; color: string }> = {
  pending: { label: 'Queued', color: 'var(--color-ink-soft)' },
  processing: { label: 'Processing', color: 'var(--color-orbit)' },
  completed: { label: 'Completed', color: '#4F7942' },
  failed: { label: 'Failed', color: '#8C2F1B' },
}

const PAGE_SIZE = 25

const STATUS_FILTERS: Array<{ value: AnalysisStatus | ''; label: string }> = [
  { value: '', label: 'Any status' },
  { value: 'pending', label: 'Queued' },
  { value: 'processing', label: 'Processing' },
  { value: 'completed', label: 'Completed' },
  { value: 'failed', label: 'Failed' },
]

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
  const { areaTotal, refreshAreas } = useDashboardContext()
  const [summary, setSummary] = useState<AnalysisSummaryResponse | null>(null)
  const [page, setPage] = useState<Analysis[]>([])
  const [status, setStatus] = useState<AnalysisStatus | ''>('')
  const [monitoredOnly, setMonitoredOnly] = useState(false)
  const [skip, setSkip] = useState(0)
  const [pageTotal, setPageTotal] = useState(0)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .analysisSummary()
      .then((data) => {
        if (!cancelled) setSummary(data)
      })
      .catch(() => {
        if (!cancelled) setLoadError('Could not load your account roll-up.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const query: AnalysisListQuery = {
    skip,
    limit: PAGE_SIZE,
    status: status === '' ? undefined : status,
    monitored_only: monitoredOnly || undefined,
  }

  const loadPage = useCallback(async () => {
    const data = await api.listAnalyses(query)
    setPage(data.items)
    setPageTotal(data.total)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, status, monitoredOnly])

  useEffect(() => {
    let cancelled = false
    loadPage().catch(() => {
      if (!cancelled) setLoadError('Could not load your areas.')
    })
    return () => {
      cancelled = true
    }
  }, [loadPage])

  const simulatedFindings = summary?.provenance['simulated'] ?? 0
  const realFindings = summary?.provenance['real'] ?? 0
  const inFlight = (summary?.by_status['pending'] ?? 0) + (summary?.by_status['processing'] ?? 0)
  const lastPage = Math.max(0, Math.ceil(pageTotal / PAGE_SIZE) - 1)
  const pageIndex = Math.floor(skip / PAGE_SIZE)

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

      {loadError && <p className="mt-6 text-sm text-[var(--color-stress)]">{loadError}</p>}

      <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Kpi
          label="Areas tracked"
          value={String(summary?.total_analyses ?? areaTotal)}
          detail={`${summary?.monitored_areas ?? 0} monitored`}
        />
        <Kpi label="Checks in flight" value={String(inFlight)} detail="queued or processing" />
        <Kpi
          label="Open alerts"
          value={String(summary?.unread_alerts ?? 0)}
          detail="not yet acknowledged"
        />
        <Kpi
          label="Checks left today"
          value={summary ? String(summary.quota_remaining_today) : '—'}
          detail={
            summary
              ? `of ${summary.quota_limit_per_day} satellite fetches`
              : 'satellite fetch quota'
          }
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Kpi
          label="Mean severity"
          value={summary?.mean_severity != null ? summary.mean_severity.toFixed(2) : '—'}
          detail={`${summary?.completed_with_findings ?? 0} findings scored`}
        />
        <Kpi
          label="Mean confidence"
          value={summary?.mean_confidence != null ? summary.mean_confidence.toFixed(2) : '—'}
          detail="across scored findings"
        />
        <Kpi
          label="Last activity"
          value={formatDate(summary?.last_activity_at ?? null)}
          detail="most recent check"
        />
        <div className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-3">
          <p className="text-xs text-[var(--color-ink-soft)]">Data behind the findings</p>
          <p className="font-tabular mt-1 text-sm font-medium">
            {realFindings} real / {simulatedFindings} simulated
          </p>
          <p className="mt-0.5 text-xs text-[var(--color-ink-soft)]">
            {simulatedFindings > 0
              ? 'Simulated findings come from the demo provider and are labelled as such.'
              : 'Every finding rests on real satellite data.'}
          </p>
        </div>
      </div>

      <section className="mt-10">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Areas
          </h2>
          <div className="flex flex-wrap items-center gap-3">
            <label className="text-xs text-[var(--color-ink-soft)]">
              <span className="sr-only">Status filter</span>
              <select
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value as AnalysisStatus | '')
                  setSkip(0)
                }}
                className="font-tabular ml-2 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-2 py-1 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
              >
                {STATUS_FILTERS.map((option) => (
                  <option key={option.label} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-1.5 text-xs text-[var(--color-ink-soft)]">
              <input
                type="checkbox"
                checked={monitoredOnly}
                onChange={(event) => {
                  setMonitoredOnly(event.target.checked)
                  setSkip(0)
                }}
                className="accent-[var(--color-orbit)]"
              />
              Monitored only
            </label>
          </div>
        </div>

        {page.length === 0 ? (
          <div className="mt-4 rounded-sm border border-[var(--color-border)] px-6 py-10 text-center">
            <p className="font-[var(--font-display)] text-lg font-semibold">
              {summary && summary.total_analyses > 0 ? 'Nothing matches this filter' : 'No areas monitored yet'}
            </p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-[var(--color-ink-soft)]">
              {summary && summary.total_analyses > 0
                ? 'Clear the filter to see the rest of your areas.'
                : 'Add a location and AURORA will check the latest cloud-free satellite pass over it for vegetation stress, land change, and more — optionally on a repeating schedule.'}
            </p>
            {(!summary || summary.total_analyses === 0) && (
              <Link
                to="/app/areas/new"
                className="mt-6 inline-block rounded-sm border border-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-orbit)] transition-colors hover:bg-[var(--color-orbit)] hover:text-[var(--color-paper)]"
              >
                Add your first area
              </Link>
            )}
          </div>
        ) : (
          <>
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
                {page.map((area) => {
                  const statusLabel = STATUS_LABELS[area.status]
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
                          {area.latitude.toFixed(3)}, {area.longitude.toFixed(3)} &middot;{' '}
                          {area.radius_km.toFixed(2)}km
                        </span>
                      </td>
                      <td className="hidden py-2 pr-4 text-[var(--color-ink-soft)] md:table-cell">
                        {ANALYSIS_TYPE_LABELS[area.analysis_type]}
                      </td>
                      <td className="py-2 pr-4">
                        <span style={{ color: statusLabel.color }}>{statusLabel.label}</span>
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

            <div className="mt-3 flex items-center justify-between text-xs text-[var(--color-ink-soft)]">
              <p className="font-tabular">
                {skip + 1}–{Math.min(skip + PAGE_SIZE, pageTotal)} of {pageTotal}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                  className="rounded-sm border border-[var(--color-border)] px-2 py-1 disabled:opacity-40"
                >
                  Newer
                </button>
                <span className="font-tabular">
                  {pageIndex + 1} / {lastPage + 1}
                </span>
                <button
                  type="button"
                  disabled={skip + PAGE_SIZE >= pageTotal}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                  className="rounded-sm border border-[var(--color-border)] px-2 py-1 disabled:opacity-40"
                >
                  Older
                </button>
                <button
                  type="button"
                  onClick={() => refreshAreas().catch(() => setLoadError('Could not refresh.'))}
                  className="ml-2 rounded-sm border border-[var(--color-border)] px-2 py-1"
                >
                  Reload
                </button>
              </div>
            </div>
          </>
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
