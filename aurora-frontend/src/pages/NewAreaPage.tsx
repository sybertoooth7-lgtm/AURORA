import { useMemo, useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDashboardContext } from '../components/Layout'
import { LocationPicker } from '../components/LocationPicker'
import { ApiError, api } from '../lib/api'
import { ANALYSIS_TYPE_LABELS, type AnalysisType } from '../lib/types'

const ANALYSIS_TYPES = Object.keys(ANALYSIS_TYPE_LABELS) as AnalysisType[]

// Nairobi -- a sensible default center given where AURORA operates, rather
// than dropping the picker at (0, 0) in the ocean off West Africa.
const DEFAULT_LATITUDE = -1.2921
const DEFAULT_LONGITUDE = 36.8219

export function NewAreaPage() {
  const navigate = useNavigate()
  const { refreshAreas } = useDashboardContext()

  const [analysisType, setAnalysisType] = useState<AnalysisType>('vegetation_stress')
  const [description, setDescription] = useState('')
  const [latitude, setLatitude] = useState(String(DEFAULT_LATITUDE))
  const [longitude, setLongitude] = useState(String(DEFAULT_LONGITUDE))
  const [radiusKm, setRadiusKm] = useState('5')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const parsedLat = Number(latitude)
  const parsedLon = Number(longitude)
  const parsedRadius = Number(radiusKm)
  // Fall back to the default center for the picker while the typed
  // coordinate is invalid/incomplete (e.g. mid-edit, or just "-"), so the
  // map never tries to render at NaN.
  const pickerLat = Number.isFinite(parsedLat) ? parsedLat : DEFAULT_LATITUDE
  const pickerLon = Number.isFinite(parsedLon) ? parsedLon : DEFAULT_LONGITUDE
  const pickerRadius = Number.isFinite(parsedRadius) && parsedRadius > 0 ? parsedRadius : 5

  const handleMapChange = useMemo(
    () => (lat: number, lon: number) => {
      setLatitude(lat.toFixed(5))
      setLongitude(lon.toFixed(5))
    },
    [],
  )

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (Number.isNaN(parsedLat) || parsedLat < -90 || parsedLat > 90) {
      setError('Latitude must be a number between -90 and 90.')
      return
    }
    if (Number.isNaN(parsedLon) || parsedLon < -180 || parsedLon > 180) {
      setError('Longitude must be a number between -180 and 180.')
      return
    }
    if (Number.isNaN(parsedRadius) || parsedRadius <= 0 || parsedRadius > 500) {
      setError('Radius must be a number between 0 and 500 km.')
      return
    }

    setSubmitting(true)
    try {
      const created = await api.createAnalysis({
        analysis_type: analysisType,
        latitude: parsedLat,
        longitude: parsedLon,
        radius_km: parsedRadius,
        description: description || undefined,
      })
      await refreshAreas()
      navigate(`/areas/${created.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create this area. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <h1 className="font-[var(--font-display)] text-2xl font-semibold">New area</h1>
      <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
        Click the map to place the area, or type coordinates directly. AURORA will check the most
        recent cloud-free satellite pass over it.
      </p>

      <div className="mt-8 grid gap-8 md:grid-cols-2">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="description" className="block text-sm font-medium">
              Name <span className="text-[var(--color-ink-soft)]">(optional)</span>
            </label>
            <input
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Naivasha flower farm, block 3"
              className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="analysisType" className="block text-sm font-medium">
              What to check for
            </label>
            <select
              id="analysisType"
              value={analysisType}
              onChange={(e) => setAnalysisType(e.target.value as AnalysisType)}
              className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            >
              {ANALYSIS_TYPES.map((type) => (
                <option key={type} value={type}>
                  {ANALYSIS_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="latitude" className="block text-sm font-medium">
                Latitude
              </label>
              <input
                id="latitude"
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                inputMode="decimal"
                required
                className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="longitude" className="block text-sm font-medium">
                Longitude
              </label>
              <input
                id="longitude"
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                inputMode="decimal"
                required
                className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label htmlFor="radius" className="block text-sm font-medium">
              Radius (km)
            </label>
            <input
              id="radius"
              value={radiusKm}
              onChange={(e) => setRadiusKm(e.target.value)}
              inputMode="decimal"
              required
              className="font-tabular mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </div>

          {error && <p className="text-sm text-[var(--color-critical)]">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? 'Submitting…' : 'Start monitoring'}
          </button>
        </form>

        <div className="h-80 overflow-hidden rounded-sm border border-[var(--color-border)] md:h-full md:min-h-80">
          <LocationPicker
            latitude={pickerLat}
            longitude={pickerLon}
            radiusKm={pickerRadius}
            onChange={handleMapChange}
          />
        </div>
      </div>
    </div>
  )
}
