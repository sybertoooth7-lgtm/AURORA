import { Navigate } from 'react-router-dom'
import { useDashboardContext } from '../components/Layout'

export function DashboardPage() {
  const { areas } = useDashboardContext()

  if (areas.length > 0) {
    return <Navigate to={`/app/areas/${areas[0].id}`} replace />
  }

  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <h1 className="font-[var(--font-display)] text-2xl font-semibold">No areas monitored yet</h1>
      <p className="mt-2 max-w-sm text-sm text-[var(--color-ink-soft)]">
        Add a location and AURORA will check it against the latest satellite pass for vegetation
        stress, land change, and more.
      </p>
    </div>
  )
}
