import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate, useOutletContext } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { Analysis } from '../lib/types'
import { ANALYSIS_TYPE_LABELS } from '../lib/types'

export interface DashboardContext {
  areas: Analysis[]
  areaTotal: number
  refreshAreas: () => Promise<void>
}

export function useDashboardContext(): DashboardContext {
  return useOutletContext<DashboardContext>()
}

// The sidebar lists areas; the dashboard pages the full table separately.
// This is the page the sidebar shows, newest first.
const SIDEBAR_PAGE_SIZE = 20

export function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [areas, setAreas] = useState<Analysis[]>([])
  const [areaTotal, setAreaTotal] = useState(0)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [resending, setResending] = useState(false)
  const [resendNote, setResendNote] = useState<string | null>(null)

  const refreshAreas = useCallback(async () => {
    const page = await api.listAnalyses({ limit: SIDEBAR_PAGE_SIZE })
    setAreas(page.items)
    setAreaTotal(page.total)
  }, [])

  useEffect(() => {
    let cancelled = false
    refreshAreas().catch(() => {
      if (!cancelled) setLoadError('Could not load your areas.')
    })
    return () => {
      cancelled = true
    }
  }, [refreshAreas])

  function handleLogout() {
    logout()
    navigate('/login')
  }

  async function handleResendVerification() {
    setResending(true)
    setResendNote(null)
    try {
      const { detail } = await api.resendEmailVerification()
      setResendNote(detail)
    } catch (err) {
      setResendNote(err instanceof Error ? err.message : 'Could not resend the verification email.')
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="flex h-full">
      <aside className="flex w-72 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-paper-raised)]">
        <div className="border-b border-[var(--color-border)] px-5 py-5">
          <Link to="/app" className="font-[var(--font-display)] text-xl font-semibold tracking-tight">
            AURORA
          </Link>
          <p className="mt-0.5 text-xs text-[var(--color-ink-soft)]">Space Intelligence</p>
        </div>

        <div className="px-5 py-4">
          <Link
            to="/app/areas/new"
            className="block w-full rounded-sm border border-[var(--color-orbit)] px-3 py-2 text-center text-sm font-medium text-[var(--color-orbit)] transition-colors hover:bg-[var(--color-orbit)] hover:text-[var(--color-paper)]"
          >
            + New area
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto px-2">
          <p className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Areas
          </p>
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
                  to={`/app/areas/${area.id}`}
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
                    {area.latitude.toFixed(3)}, {area.longitude.toFixed(3)} &middot;{' '}
                    {area.radius_km.toFixed(2)}km
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
          {areaTotal > areas.length && (
            <p className="font-tabular px-3 pt-1 text-xs text-[var(--color-ink-soft)]">
              {areas.length} of {areaTotal} shown &middot; see Overview for the rest
            </p>
          )}

          <p className="px-3 pb-1 pt-4 text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Field operations
          </p>
          <ul className="space-y-0.5">
            <li>
              <SideLink to="/app/fields">Crop field analysis</SideLink>
            </li>
            <li>
              <SideLink to="/app/fleet">Flights &amp; telemetry</SideLink>
            </li>
          </ul>

          <p className="px-3 pb-1 pt-4 text-xs font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
            Platform
          </p>
          <ul className="space-y-0.5">
            <li>
              <SideLink to="/app/operations">Job pipeline</SideLink>
            </li>
            <li>
              <SideLink to="/app/divisions">Division simulations</SideLink>
            </li>
          </ul>
        </nav>

        <div className="border-t border-[var(--color-border)] px-5 py-4">
          <NavLink
            to="/app/settings"
            className={({ isActive }) =>
              `block rounded-sm px-3 py-2 text-sm ${
                isActive ? 'bg-[var(--color-orbit)] text-[var(--color-paper)]' : 'hover:bg-[var(--color-paper)]'
              }`
            }
          >
            Settings &amp; API keys
          </NavLink>
          <p className="mt-2 truncate text-sm font-medium">{user?.username}</p>
          <button
            type="button"
            onClick={handleLogout}
            className="mt-1 text-sm text-[var(--color-ink-soft)] underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-ink)]"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        {user && !user.email_verified && (
          <div className="border-b border-[var(--color-border)] bg-[var(--color-paper-raised)] px-8 py-2.5 text-sm">
            <span className="text-[var(--color-ink-soft)]">
              Verify your email to run first-of-kind jobs (new analyses, AI inference, fleet
              operations).
            </span>{' '}
            <button
              type="button"
              onClick={handleResendVerification}
              disabled={resending}
              className="underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-orbit)] disabled:opacity-50"
            >
              {resending ? 'Resending…' : 'Resend email'}
            </button>
            {resendNote && <span className="ml-2 text-[var(--color-ink-soft)]">{resendNote}</span>}
          </div>
        )}
        <div className="min-h-0 flex-1">
          <Outlet
            context={{
              areas,
              areaTotal,
              refreshAreas,
            }}
          />
        </div>
      </main>
    </div>
  )
}

function SideLink({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `block rounded-sm px-3 py-2 text-sm ${
          isActive ? 'bg-[var(--color-orbit)] text-[var(--color-paper)]' : 'hover:bg-[var(--color-paper)]'
        }`
      }
    >
      {children}
    </NavLink>
  )
}
