import type { ReactNode } from 'react'
import type { SimulationEnvelope } from '../lib/simulation'

/**
 * The one honesty rule for the division surfaces: a number produced by Stage 0
 * model code is never allowed to render on its own. Every panel that shows one
 * goes through this component, so the provenance flag and the list of what the
 * model leaves out travel with the figure.
 */
export function SimulationPanel({
  title,
  description,
  envelope,
  children,
}: {
  title: string
  description?: string
  envelope: SimulationEnvelope | null
  children: ReactNode
}) {
  return (
    <section className="panel">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <h3 className="eyebrow text-[var(--color-ink)]">{title}</h3>
          {description && <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{description}</p>}
        </div>
        {envelope && <ProvenanceBadge provenance={envelope.provenance} stage={envelope.stage} />}
      </header>

      <div className="px-4 py-4">{children}</div>

      {envelope && envelope.model_limitations.length > 0 && (
        <details className="border-t border-[var(--color-border)] px-4 py-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            What this model leaves out
          </summary>
          <ul className="mt-2 space-y-1.5 text-sm text-[var(--color-ink-soft)]">
            {envelope.model_limitations.map((line) => (
              <li key={line} className="flex gap-2">
                <span aria-hidden className="text-[var(--color-stress)]">
                  &middot;
                </span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

export function ProvenanceBadge({
  provenance,
  stage,
}: {
  provenance: 'real' | 'simulated'
  stage?: string
}) {
  const simulated = provenance === 'simulated'
  return (
    <span
      className="rounded-sm border px-2 py-1 text-xs font-medium"
      style={{
        borderColor: simulated ? 'var(--color-stress)' : 'var(--color-healthy)',
        color: simulated ? 'var(--color-stress)' : 'var(--color-healthy)',
      }}
      title={stage ? `Code maturity: ${stage}` : undefined}
    >
      {simulated ? 'Simulated' : 'Real data'}
    </span>
  )
}

export function Readout({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-[var(--color-ink-soft)]">{label}</p>
      <p className="font-tabular mt-0.5 text-sm font-medium">{value}</p>
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p className="text-sm" style={{ color: 'var(--color-critical)' }}>
      {message}
    </p>
  )
}

export function describeApiError(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) {
    // FastAPI validation errors put an array in `detail`; a plain sentence is
    // more useful in the UI than "[object Object]".
    return err.message === '[object Object]' ? fallback : err.message
  }
  return fallback
}
