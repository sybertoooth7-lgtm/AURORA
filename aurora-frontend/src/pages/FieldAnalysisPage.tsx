import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FieldBoundaryMap, toFieldBoundary, type FieldVertex } from '../components/FieldBoundaryMap'
import { ProvenanceBadge, Readout, describeApiError } from '../components/SimulationPanel'
import { api } from '../lib/api'
import { severityColor } from '../lib/colors'
import type { CropAnalysisResponse, CropBulkAnalysisResponse, FieldBoundary } from '../lib/types'

const MAX_BATCH_FIELDS = 25

interface BatchField {
  label: string
  boundary: FieldBoundary
}

function conditionColor(condition: string): string {
  if (condition === 'healthy') return 'var(--color-healthy)'
  if (condition === 'stressed') return 'var(--color-stress)'
  return 'var(--color-critical)'
}

export function FieldAnalysisPage() {
  const [vertices, setVertices] = useState<FieldVertex[]>([])
  const [batch, setBatch] = useState<BatchField[]>([])
  const [description, setDescription] = useState('')
  const [useHistory, setUseHistory] = useState(true)
  const [running, setRunning] = useState<'single' | 'batch' | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<CropAnalysisResponse | null>(null)
  const [bulk, setBulk] = useState<CropBulkAnalysisResponse | null>(null)

  const boundary = toFieldBoundary(vertices)

  function addVertex(lat: number, lng: number) {
    setError(null)
    setVertices((current) => [...current, { lat, lng }])
  }

  function undoVertex() {
    setVertices((current) => current.slice(0, -1))
  }

  function queueCurrentField() {
    if (!boundary) {
      setError('Draw at least three vertices before adding a field to the batch.')
      return
    }
    setBatch((current) => [
      ...current,
      { label: description.trim() || `Field ${current.length + 1}`, boundary },
    ])
    setVertices([])
    setDescription('')
    setResult(null)
  }

  async function runSingle() {
    if (!boundary) {
      setError('Click on the map to trace the field boundary first — a ring needs at least three vertices.')
      return
    }
    setRunning('single')
    setError(null)
    try {
      const analysis = await api.analyzeField({
        field_boundary: boundary,
        use_history: useHistory,
        description: description.trim() || undefined,
      })
      setResult(analysis)
      setBulk(null)
    } catch (err) {
      setError(describeApiError(err, 'The analysis could not run.'))
    } finally {
      setRunning(null)
    }
  }

  async function runBatch() {
    if (batch.length === 0) {
      setError('Add at least one drawn field to the batch.')
      return
    }
    setRunning('batch')
    setError(null)
    try {
      const response = await api.analyzeFields({
        fields: batch.map((field) => ({ label: field.label, field_boundary: field.boundary })),
        use_history: useHistory,
      })
      setBulk(response)
      setResult(null)
    } catch (err) {
      setError(describeApiError(err, 'The batch could not run.'))
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header className="flex items-end justify-between gap-4">
        <div>
          <h1 className="font-[var(--font-display)] text-2xl font-semibold">Crop field analysis</h1>
          <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-soft)]">
            Trace a field boundary and AURORA measures NDVI over the covering satellite area,
            classifies crop condition and stores the run as a monitored analysis. A boundary, not a
            point and a radius, because a field is not a circle.
          </p>
        </div>
        <Link
          to="/app/areas/new"
          className="shrink-0 text-sm text-[var(--color-orbit)] underline decoration-[var(--color-border)] underline-offset-2"
        >
          Point + radius instead
        </Link>
      </header>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="eyebrow">
            Boundary
          </h2>
          <div className="mt-3 h-80 overflow-hidden rounded-sm border border-[var(--color-border)]">
            <FieldBoundaryMap vertices={vertices} onAddVertex={addVertex} />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={undoVertex}
              disabled={vertices.length === 0}
              className="btn btn-secondary px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Remove vertex
            </button>
            <button
              type="button"
              onClick={() => setVertices([])}
              disabled={vertices.length === 0}
              className="btn btn-secondary px-3 py-1.5 text-sm disabled:opacity-40"
            >
              Clear
            </button>
            <p className="font-tabular text-xs text-[var(--color-ink-soft)]">
              {vertices.length} vertices
              {vertices.length > 0 && !boundary ? ' (need 3 to close)' : ''}
            </p>
          </div>

          <label className="mt-4 block">
            <span className="text-xs text-[var(--color-ink-soft)]">Description (optional)</span>
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              maxLength={200}
              placeholder="North maize field"
              className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </label>

          <label className="mt-3 flex items-center gap-2 text-sm text-[var(--color-ink-soft)]">
            <input
              type="checkbox"
              checked={useHistory}
              onChange={(event) => setUseHistory(event.target.checked)}
              className="accent-[var(--color-orbit)]"
            />
            Compare against the previous pass when one exists
          </label>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={runSingle}
              disabled={running !== null}
              className="btn btn-primary px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {running === 'single' ? 'Analysing…' : 'Analyse this field'}
            </button>
            <button
              type="button"
              onClick={queueCurrentField}
              disabled={running !== null}
              className="btn btn-outline px-4 py-2 text-sm font-medium text-[var(--color-orbit)] transition-colors hover:bg-[var(--color-orbit)] hover:text-[var(--color-paper)] disabled:opacity-50"
            >
              Add to batch
            </button>
          </div>

          {error && (
            <p className="mt-3 text-sm" style={{ color: 'var(--color-critical)' }}>
              {error}
            </p>
          )}
        </section>

        <section>
          <h2 className="eyebrow">
            Batch ({batch.length}/{MAX_BATCH_FIELDS})
          </h2>
          {batch.length === 0 ? (
            <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
              No fields queued. Draw a boundary, then use “Add to batch” to build a whole-farm run;
              one submission costs one round trip and a bad boundary only fails its own field.
            </p>
          ) : (
            <ul className="mt-3 space-y-1.5">
              {batch.map((field, index) => (
                <li
                  key={`${field.label}-${index}`}
                  className="flex items-center justify-between rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm"
                >
                  <span className="truncate">{field.label}</span>
                  <span className="font-tabular shrink-0 text-xs text-[var(--color-ink-soft)]">
                    {field.boundary.coordinates[0].length - 1} vertices
                  </span>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex gap-3">
            <button
              type="button"
              onClick={runBatch}
              disabled={running !== null || batch.length === 0}
              className="btn btn-primary px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {running === 'batch' ? 'Running…' : `Run batch (${batch.length})`}
            </button>
            <button
              type="button"
              onClick={() => {
                setBatch([])
                setBulk(null)
              }}
              disabled={batch.length === 0}
              className="btn btn-secondary px-4 py-2 text-sm disabled:opacity-40"
            >
              Clear batch
            </button>
          </div>
          <p className="mt-3 text-xs text-[var(--color-ink-soft)]">
            Runs cost against your daily satellite fetch quota, and first-of-kind jobs need a
            verified email.
          </p>
        </section>
      </div>

      {result && <FieldReport result={result} />}
      {bulk && <BulkReport bulk={bulk} />}
    </div>
  )
}

function FieldReport({ result }: { result: CropAnalysisResponse }) {
  const colors = severityColor(result.severity)
  return (
    <section className="mt-10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="eyebrow">
          Report
        </h2>
        <ProvenanceBadge provenance={result.provenance} />
      </div>

      <div className="mt-3 panel px-4 py-4">
        <div className="flex flex-wrap items-center gap-4">
          <p
            className="rounded-sm px-3 py-1 text-sm font-semibold"
            style={{ backgroundColor: colors.bg, color: conditionColor(result.condition) }}
          >
            {result.condition}
          </p>
          <Link
            to={`/app/areas/${result.analysis_id}`}
            className="text-sm text-[var(--color-orbit)] underline decoration-[var(--color-border)] underline-offset-2"
          >
            Open the stored analysis #{result.analysis_id}
          </Link>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Readout label="NDVI" value={result.ndvi.toFixed(3)} />
          <Readout label="Change score" value={result.change_score.toFixed(3)} />
          <Readout label="Severity" value={result.severity.toFixed(2)} />
          <Readout label="Confidence" value={result.confidence.toFixed(2)} />
        </div>

        <div className="font-tabular mt-4 grid grid-cols-2 gap-4 border-t border-[var(--color-border)] pt-4 text-xs text-[var(--color-ink-soft)] sm:grid-cols-4">
          <p>survey centre {result.latitude.toFixed(4)}, {result.longitude.toFixed(4)}</p>
          <p>covering radius {result.radius_km.toFixed(2)} km</p>
          <p>cloud {Math.round(result.observation.cloud_coverage * 100)}%</p>
          <p>pass {new Date(result.observation.acquired_at).toLocaleDateString()}</p>
        </div>

        <ul className="mt-4 space-y-1.5 text-sm">
          {result.report.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>

        {result.provenance === 'simulated' && (
          <p className="mt-4 text-sm" style={{ color: 'var(--color-stress)' }}>
            This run used the demo provider’s synthetic imagery. The numbers exercise the pipeline,
            not the field.
          </p>
        )}
      </div>
    </section>
  )
}

function BulkReport({ bulk }: { bulk: CropBulkAnalysisResponse }) {
  return (
    <section className="mt-10">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="eyebrow">
          Batch results
        </h2>
        <p className="font-tabular text-xs text-[var(--color-ink-soft)]">
          {bulk.succeeded} ok · {bulk.failed} failed · {bulk.real} real / {bulk.simulated} simulated
        </p>
      </div>

      <table className="mt-3 w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
            <th className="py-2 font-medium">Field</th>
            <th className="py-2 font-medium">Condition</th>
            <th className="hidden py-2 font-medium sm:table-cell">NDVI</th>
            <th className="py-2 font-medium">Severity</th>
            <th className="hidden py-2 font-medium md:table-cell">Source</th>
          </tr>
        </thead>
        <tbody>
          {bulk.items.map((item, index) => {
            const analysis = item.analysis
            const colors = severityColor(analysis?.severity ?? null)
            return (
              <tr key={`${item.label ?? 'field'}-${index}`} className="border-b border-[var(--color-border)]">
                <td className="py-2 pr-4">
                  {analysis ? (
                    <Link
                      to={`/app/areas/${analysis.analysis_id}`}
                      className="font-medium underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-orbit)]"
                    >
                      {item.label ?? `Field ${index + 1}`}
                    </Link>
                  ) : (
                    <span className="font-medium">{item.label ?? `Field ${index + 1}`}</span>
                  )}
                  {item.error && (
                    <span className="block text-xs" style={{ color: 'var(--color-critical)' }}>
                      {item.error}
                    </span>
                  )}
                </td>
                <td className="py-2 pr-4">
                  {analysis ? (
                    <span style={{ color: conditionColor(analysis.condition) }}>{analysis.condition}</span>
                  ) : (
                    <span className="text-[var(--color-ink-soft)]">—</span>
                  )}
                </td>
                <td className="font-tabular hidden py-2 pr-4 sm:table-cell">
                  {analysis ? analysis.ndvi.toFixed(3) : '—'}
                </td>
                <td className="py-2 pr-4">
                  {analysis ? (
                    <span
                      className="font-tabular rounded-sm px-2 py-0.5 text-xs font-medium"
                      style={{ backgroundColor: colors.bg, color: colors.text }}
                    >
                      {analysis.severity.toFixed(2)}
                    </span>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="font-tabular hidden py-2 text-[var(--color-ink-soft)] md:table-cell">
                  {analysis ? `${analysis.observation.source}${analysis.observation.simulated ? ' (simulated)' : ''}` : '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {bulk.simulated > 0 && (
        <p className="mt-3 text-sm" style={{ color: 'var(--color-stress)' }}>
          {bulk.simulated} of {bulk.requested} fields rest on synthetic imagery. Comparing them
          against real passes compares a model against a measurement.
        </p>
      )}
    </section>
  )
}
