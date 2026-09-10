import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate, useOutletContext } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Analysis } from '../lib/types'
import { ANALYSIS_TYPE_LABELS } from '../lib/types'

export interface DashboardContext {
  areas: Analysis[]
  refreshAreas: () => Promise<void>
}

export function useDashboardContext(): DashboardContext {
  return useOutletContext<DashboardContext>()
}

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [areas, setAreas] = useState<Analysis[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    api
      .listAnalyses()
      .then((data) => {
        if (!cancelled) setAreas(data)
      })
      .catch(() => {
        if (!cancelled) setLoadError('Could not load your areas.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  function handleLogout() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-full">
      <aside className="flex w-72 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-paper-raised)]">
        <div className="border-b border-[var(--color-border)] px-5 py-5">
          <Link to="/" className="font-[var(--font-display)] text-xl font-semibold tracking-tight">
            AURORA
          </Link>
          <p className="mt-0.5 text-xs text-[var(--color-ink-soft)]">Space Intelligence</p>
        </div>

        <div className="px-5 py-4">
          <Link
            to="/areas/new"
            className="block w-full rounded-sm border border-[var(--color-orbit)] px-3 py-2 text-center text-sm font-medium text-[var(--color-orbit)] transition-colors hover:bg-[var(--color-orbit)] hover:text-[var(--color-paper)]"
          >
            + New area
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-2">
          {loadError && <p className="px-3 py-2 text-sm text-[var(--color-stress)]">{loadError}</p>}
          {!loadError && areas.length === 0 && (
            <p className="px-3 py-2 text-sm text-[var(--color-ink-soft)]">
              No areas yet. Add your first one above.
            </p>
          )}
          <ul className="space-y-0.5">
            {areas.map((area) => (
              <li key={area.id}>
                <NavLink
                  to={`/areas/${area.id}`}
                  className={({ isActive }) =>
                    `block rounded-sm px-3 py-2 text-sm ${
                      isActive ? 'bg-[var(--color-orbit)] text-[var(--color-paper)]' : 'hover:bg-[var(--color-paper)]'
                    }`
                  }
                >
                  <span className="block truncate font-medium">
                    {area.description || ANALYSIS_TYPE_LABELS[area.analysis_type]}
                  </span>
                  <span className="font-tabular block truncate text-xs opacity-75">
                    {area.latitude.toFixed(3)}, {area.longitude.toFixed(3)} &middot; {area.radius_km}km
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="border-t border-[var(--color-border)] px-5 py-4">
          <p className="truncate text-sm font-medium">{user?.username}</p>
          <button
            type="button"
            onClick={handleLogout}
            className="mt-1 text-sm text-[var(--color-ink-soft)] underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-ink)]"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <Outlet
          context={{
            areas,
            refreshAreas: () => api.listAnalyses().then((data) => setAreas(data)),
          }}
        />
      </main>
    </div>
  )
}
