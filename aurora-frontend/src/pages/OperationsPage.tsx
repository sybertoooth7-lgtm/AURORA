import { useCallback, useEffect, useState } from 'react'
import { ErrorNote, SimulationPanel } from '../components/SimulationPanel'
import { ApiError, api } from '../lib/api'
import { JOB_COUNTER_LABELS, type AnalysisStatus, type JobPipelineStatus } from '../lib/types'
import type { DataReadinessResponse } from '../lib/simulation'

interface StuckAnalysis {
  id: number
  user_id: number
  status: AnalysisStatus
  analysis_type: string
  created_at: string | null
}

const COUNTER_ORDER = ['enqueued', 'completed', 'failed', 'retried', 'cache_hit', 'cache_miss']

function reasonMessage(reason: unknown, fallback: string): string {
  return reason instanceof Error && reason.message ? reason.message : fallback
}

function formatTime(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  })
}

export function OperationsPage() {
  const [jobs, setJobs] = useState<JobPipelineStatus | null>(null)
  const [readiness, setReadiness] = useState<DataReadinessResponse | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [adminOnly, setAdminOnly] = useState(false)

  const load = useCallback(async () => {
    setErrors([])
    const [jobResult, readinessResult] = await Promise.allSettled([
      api.jobPipelineStatus(),
      api.dataReadiness(),
    ])
    // Both halves can fail at once (a rate limit takes out the whole page), and
    // each reason is worth reading -- collecting them keeps the second failure
    // from overwriting the first.
    const problems: string[] = []
    if (jobResult.status === 'fulfilled') {
      setJobs(jobResult.value)
      setAdminOnly(false)
    } else {
      setJobs(null)
      const reason = jobResult.reason
      if (reason instanceof ApiError && reason.status === 403) setAdminOnly(true)
      else problems.push(reasonMessage(reason, 'Could not read the job pipeline.'))
    }
    if (readinessResult.status === 'fulfilled') {
      setReadiness(readinessResult.value)
    } else {
      setReadiness(null)
      problems.push(reasonMessage(readinessResult.reason, 'Data readiness unavailable.'))
    }
    setErrors(problems)
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-[var(--font-display)] text-2xl font-semibold">Pipeline operations</h1>
          <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-soft)]">
            What the background analysis queue is doing right now, and whether it is safe to
            schedule more monitoring work. Queue counters and database state are shown side by
            side on purpose: a job lost to a worker crash leaves its row pending forever, which an
            empty queue cannot reveal.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-sm border border-[var(--color-border)] px-3 py-1.5 text-sm"
        >
          Reload
        </button>
      </header>

      {errors.length > 0 && (
        <div className="mt-6 space-y-2">
          {errors.map((message) => (
            <ErrorNote key={message} message={message} />
          ))}
        </div>
      )}
      {adminOnly && (
        <p className="mt-6 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-3 text-sm text-[var(--color-ink-soft)]">
          The queue view is for platform operators. Data readiness below is available to your
          account.
        </p>
      )}

      {jobs && <QueueCards jobs={jobs} />}

      {jobs && (
        <section className="mt-10">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Today
          </h2>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {COUNTER_ORDER.map((name) => (
              <div
                key={name}
                className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2"
              >
                <p className="text-xs text-[var(--color-ink-soft)]">{JOB_COUNTER_LABELS[name] ?? name}</p>
                <p className="font-tabular mt-1 text-lg font-semibold">
                  {jobs.today.counters[name] ?? 0}
                </p>
              </div>
            ))}
          </div>
          <p className="font-tabular mt-3 text-sm text-[var(--color-ink-soft)]">
            {jobs.today.day} · success rate{' '}
            {jobs.today.success_rate == null ? 'no attempts yet' : `${(jobs.today.success_rate * 100).toFixed(1)}%`}
          </p>

          <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Recent failures
          </h3>
          {jobs.today.recent_failures.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--color-ink-soft)]">Nothing failed today.</p>
          ) : (
            <table className="mt-3 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                  <th className="py-2 font-medium">Analysis</th>
                  <th className="py-2 font-medium">Attempt</th>
                  <th className="hidden py-2 font-medium sm:table-cell">When</th>
                  <th className="py-2 font-medium">Error</th>
                </tr>
              </thead>
              <tbody>
                {jobs.today.recent_failures.map((failure) => (
                  <tr key={`${failure.analysis_id}-${failure.at}`} className="border-b border-[var(--color-border)]">
                    <td className="font-tabular py-2 pr-4">#{failure.analysis_id}</td>
                    <td className="font-tabular py-2 pr-4">{failure.attempt}</td>
                    <td className="font-tabular hidden py-2 pr-4 text-[var(--color-ink-soft)] sm:table-cell">
                      {formatTime(failure.at)}
                    </td>
                    <td className="py-2">{failure.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 className="mt-8 text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Stuck analyses
          </h3>
          {jobs.stuck_analyses.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--color-ink-soft)]">
              No row has been left pending or processing past three job timeouts.
            </p>
          ) : (
            <ul className="mt-3 space-y-1.5">
              {jobs.stuck_analyses.map((row) => (
                <StuckRow key={row.id} row={row} />
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="mt-10">
        <SimulationPanel
          title="Data source readiness"
          description="Inferred from this platform's own job outcomes today, not from a provider health probe."
          envelope={readiness}
        >
          {!readiness ? (
            <p className="text-sm text-[var(--color-ink-soft)]">No readiness data.</p>
          ) : (
            <>
              <p className="font-tabular text-sm">
                overall: <span className="font-semibold">{readiness.overall}</span>
              </p>
              <p className="mt-2 text-sm text-[var(--color-ink-soft)]">{readiness.basis}</p>
              <table className="mt-4 w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                    <th className="py-2 font-medium">Source</th>
                    <th className="hidden py-2 font-medium sm:table-cell">Provider</th>
                    <th className="py-2 font-medium">Status</th>
                    <th className="py-2 font-medium">Schedulable</th>
                  </tr>
                </thead>
                <tbody>
                  {readiness.sources.map((source) => (
                    <tr key={source.name} className="border-b border-[var(--color-border)]">
                      <td className="py-2 pr-4">{source.name}</td>
                      <td className="hidden py-2 pr-4 text-[var(--color-ink-soft)] sm:table-cell">
                        {source.provider}
                      </td>
                      <td className="py-2 pr-4">{source.status}</td>
                      <td className="font-tabular py-2">{source.schedulable ? 'yes' : 'no'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </SimulationPanel>
      </section>
    </div>
  )
}

function QueueCards({ jobs }: { jobs: JobPipelineStatus }) {
  const cards = [
    {
      label: 'Queue',
      value: jobs.queue.name ?? 'unknown',
      detail: jobs.queue.inline_execution
        ? 'inline execution (demo mode: jobs run in the request)'
        : `depth ${jobs.queue.depth}`,
    },
    {
      label: 'Job timeout',
      value: `${jobs.job_policy.timeout_seconds}s`,
      detail: `${jobs.job_policy.max_retries} retries, ${jobs.job_policy.retry_backoff_seconds}s backoff`,
    },
    {
      label: 'Observation cache',
      value: jobs.observation_cache.enabled ? `${jobs.observation_cache.ttl_seconds}s` : 'off',
      detail:
        jobs.observation_cache.enabled
          ? `hit/miss today ${jobs.today.counters['cache_hit'] ?? 0}/${jobs.today.counters['cache_miss'] ?? 0}`
          : 'every request fetches live',
    },
    {
      label: 'Monitored areas',
      value: String(jobs.monitoring.monitored_areas),
      detail: `scheduler tick ${jobs.monitoring.tick_seconds}s, min interval ${jobs.monitoring.min_interval_minutes}min`,
    },
  ]

  return (
    <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-4 py-3"
        >
          <p className="text-xs text-[var(--color-ink-soft)]">{card.label}</p>
          <p className="font-tabular mt-1 truncate text-lg font-semibold">{card.value}</p>
          <p className="mt-0.5 text-xs text-[var(--color-ink-soft)]">{card.detail}</p>
        </div>
      ))}
    </div>
  )
}

function StuckRow({ row }: { row: StuckAnalysis }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm">
      <span>
        <span className="font-tabular">#{row.id}</span> {row.analysis_type}
      </span>
      <span className="font-tabular text-xs text-[var(--color-ink-soft)]">
        {row.status} since {formatTime(row.created_at)} · owner {row.user_id}
      </span>
    </li>
  )
}
