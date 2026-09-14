import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AreaMap } from '../components/AreaMap'
import { api } from '../lib/api'
import { severityColor, alertColor } from '../lib/colors'
import {
  ANALYSIS_TYPE_LABELS,
  MONITORING_CADENCES,
  monitoringCadenceLabel,
  parseResultMetadata,
  type Alert,
  type Analysis,
  type AnalysisResult,
} from '../lib/types'

const POLL_INTERVAL_MS = 3000

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function AreaDetailPage() {
  const params = useParams<{ id: string }>()
  const analysisId = Number(params.id)

  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [results, setResults] = useState<AnalysisResult[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [notFound, setNotFound] = useState(false)
  const [cadence, setCadence] = useState<number | null>(null)
  const [savingCadence, setSavingCadence] = useState(false)
  const [rerunning, setRerunning] = useState(false)

  useEffect(() => {
    setAnalysis(null)
    setResults([])
    setAlerts([])
    setNotFound(false)
    setCadence(null)
  }, [analysisId])

  const refresh = useCallback(async () => {
    const [freshAnalysis, resultData, alertData] = await Promise.all([
      api.getAnalysis(analysisId),
      api.getAnalysisResults(analysisId),
      api.listAlerts(),
    ])
    setAnalysis(freshAnalysis)
    setCadence(freshAnalysis.monitor_interval_minutes)
    setResults(resultData.results)
    setAlerts(alertData)
    return freshAnalysis.status
  }, [analysisId])

  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const status = await refresh()
        if (cancelled) return
        if (status === 'pending' || status === 'processing') {
          timer = setTimeout(poll, POLL_INTERVAL_MS)
        }
      } catch {
        if (!cancelled) setNotFound(true)
      }
    }

    poll()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [refresh, analysisId])

  const lastKnownCadence = analysis?.monitor_interval_minutes ?? null
  async function handleCadenceChange(value: number | null) {
    setCadence(value)
    setSavingCadence(true)
    try {
      const updated = await api.setMonitoring(analysisId, value)
      setAnalysis(updated)
    } catch {
      setCadence(lastKnownCadence)
    } finally {
      setSavingCadence(false)
    }
  }

  async function handleRerun() {
    setRerunning(true)
    try {
      await api.rerunAnalysis(analysisId)
      await refresh()
    } catch {
      // 409 while a run is in flight -- the poll loop picks up the new state.
    } finally {
      setRerunning(false)
    }
  }

  if (notFound) {
    return (
      <div className="px-6 py-10">
        <p className="text-sm text-[var(--color-critical)]">
          This area doesn't exist, or isn't yours.
        </p>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="px-6 py-10">
        <p className="text-sm text-[var(--color-ink-soft)]">Loading…</p>
      </div>
    )
  }

  const latestResult = results[results.length - 1] ?? null
  const metadata = latestResult ? parseResultMetadata(latestResult) : null
  const relevantAlerts = alerts.filter((alert) =>
    results.some((result) => result.id === alert.analysis_result_id),
  )
  const runActive = analysis.status === 'pending' || analysis.status === 'processing'

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-[var(--color-border)] px-6 py-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-[var(--font-display)] text-xl font-semibold">
              {analysis.description || ANALYSIS_TYPE_LABELS[analysis.analysis_type]}
            </h1>
            <p className="font-tabular mt-0.5 text-sm text-[var(--color-ink-soft)]">
              {analysis.latitude.toFixed(4)}, {analysis.longitude.toFixed(4)} &middot;{' '}
              {analysis.radius_km}km radius
            </p>
          </div>
          <span className="font-tabular shrink-0 rounded-sm border border-[var(--color-border)] px-2 py-1 text-xs font-medium text-[var(--color-ink-soft)]">
            {monitoringCadenceLabel(cadence)}
          </span>
        </div>
      </header>

      <div className="h-72 shrink-0 border-b border-[var(--color-border)]">
        <AreaMap
          latitude={analysis.latitude}
          longitude={analysis.longitude}
          radiusKm={analysis.radius_km}
          ndvi={metadata?.ndvi}
        />
      </div>

      <StatusStrip analysis={analysis} result={latestResult} metadata={metadata} />

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <section className="mt-8 first:mt-0">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Monitoring
          </h2>
          <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-3 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-3">
            <div>
              <label
                htmlFor="cadence"
                className="block text-xs text-[var(--color-ink-soft)]"
              >
                Re-check this area
              </label>
              <select
                id="cadence"
                value={cadence ?? ''}
                disabled={savingCadence}
                onChange={(e) =>
                  handleCadenceChange(e.target.value === '' ? null : Number(e.target.value))
                }
                className="font-tabular mt-1 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none disabled:opacity-50"
              >
                <option value="">Off (one-off check)</option>
                {MONITORING_CADENCES.map((c) => (
                  <option key={c.minutes} value={c.minutes}>
                    {c.label}
                  </option>
                ))}
              </select>
            </div>

            {cadence != null && (
              <div className="font-tabular text-xs text-[var(--color-ink-soft)]">
                <p>
                  Next check{' '}
                  <span className="text-[var(--color-ink)]">{formatDateTime(analysis.next_check_at)}</span>
                </p>
                <p>
                  Last check{' '}
                  <span className="text-[var(--color-ink)]">{formatDateTime(analysis.completed_at)}</span>
                </p>
              </div>
            )}

            <button
              type="button"
              onClick={handleRerun}
              disabled={runActive || rerunning}
              className="ml-auto rounded-sm border border-[var(--color-orbit)] px-3 py-2 text-sm font-medium text-[var(--color-orbit)] transition-colors hover:bg-[var(--color-orbit)] hover:text-[var(--color-paper)] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {rerunning ? 'Running…' : runActive ? 'Already running' : 'Re-run now'}
            </button>
          </div>
        </section>

        <section className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Alerts
          </h2>
          {relevantAlerts.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--color-ink-soft)]">No alerts for this area.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {relevantAlerts.map((alert) => {
                const colors = alertColor(alert.alert_type)
                return (
                  <li
                    key={alert.id}
                    className="rounded-sm border border-[var(--color-border)] px-4 py-3"
                    style={{ backgroundColor: colors.bg }}
                  >
                    <p className="text-sm font-medium" style={{ color: colors.text }}>
                      {alert.title}
                    </p>
                    <p className="mt-0.5 text-sm text-[var(--color-ink-soft)]">{alert.description}</p>
                    <p className="font-tabular mt-1 text-xs text-[var(--color-ink-soft)]">
                      {new Date(alert.created_at).toLocaleString()}
                    </p>
                  </li>
                )
              })}
            </ul>
          )}
        </section>

        <section className="mt-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            History
          </h2>
          {results.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--color-ink-soft)]">No results yet.</p>
          ) : (
            <table className="mt-3 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                  <th className="py-2 font-medium">Date</th>
                  <th className="py-2 font-medium">Pass</th>
                  <th className="py-2 font-medium">Finding</th>
                  <th className="py-2 font-medium">Severity</th>
                </tr>
              </thead>
              <tbody>
                {[...results].reverse().map((result) => {
                  const colors = severityColor(result.severity_score)
                  const rowMeta = parseResultMetadata(result)
                  return (
                    <tr key={result.id} className="border-b border-[var(--color-border)]">
                      <td className="font-tabular py-2 text-[var(--color-ink-soft)]">
                        {new Date(result.created_at).toLocaleDateString()}
                      </td>
                      <td className="font-tabular py-2 text-[var(--color-ink-soft)]">
                        {rowMeta?.acquired_at
                          ? new Date(rowMeta.acquired_at).toLocaleDateString()
                          : '—'}
                      </td>
                      <td className="py-2">{result.finding}</td>
                      <td className="py-2">
                        <span
                          className="font-tabular rounded-sm px-2 py-0.5 text-xs font-medium"
                          style={{ backgroundColor: colors.bg, color: colors.text }}
                        >
                          {result.severity_score != null ? result.severity_score.toFixed(2) : '—'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </div>
  )
}

function StatusStrip({
  analysis,
  result,
  metadata,
}: {
  analysis: Analysis
  result: AnalysisResult | null
  metadata: ReturnType<typeof parseResultMetadata>
}) {
  if (analysis.status === 'pending' || analysis.status === 'processing') {
    return (
      <div className="border-b border-[var(--color-border)] bg-[var(--color-paper-raised)] px-6 py-3">
        <p className="text-sm text-[var(--color-ink-soft)]">
          {analysis.status === 'pending' ? 'Queued for processing…' : 'Fetching the latest pass…'}
        </p>
      </div>
    )
  }

  if (analysis.status === 'failed') {
    return (
      <div
        className="border-b border-[var(--color-border)] px-6 py-3"
        style={{ backgroundColor: '#EFD0C6' }}
      >
        <p className="text-sm font-medium" style={{ color: '#8C2F1B' }}>
          This analysis failed. Try re-running it, or check back later.
        </p>
      </div>
    )
  }

  if (!result || !metadata) {
    return (
      <div className="border-b border-[var(--color-border)] bg-[var(--color-paper-raised)] px-6 py-3">
        <p className="text-sm text-[var(--color-ink-soft)]">No readings yet.</p>
      </div>
    )
  }

  return (
    <div className="font-tabular grid grid-cols-2 gap-4 border-b border-[var(--color-border)] bg-[var(--color-paper-raised)] px-6 py-3 text-sm sm:grid-cols-4">
      <Reading label="NDVI" value={metadata.ndvi.toFixed(2)} />
      <Reading label="Change score" value={metadata.change_score.toFixed(2)} />
      <Reading label="Cloud cover" value={`${(metadata.cloud_coverage * 100).toFixed(0)}%`} />
      <Reading label="Last pass" value={new Date(metadata.acquired_at).toLocaleDateString()} />
    </div>
  )
}

function Reading({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-[var(--color-ink-soft)]">{label}</p>
      <p className="text-base font-medium">{value}</p>
    </div>
  )
}