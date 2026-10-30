import { lazy, Suspense } from 'react'
import { Navigate, Route, BrowserRouter, Routes } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Layout } from './components/Layout'
import { AuthProvider, useAuth } from './lib/auth'
import { LandingPage } from './pages/LandingPage'

// The landing page is the public entry and stays eager. Everything behind it
// is split by route: the console pulls in Leaflet (map screens) and the fleet
// charts, and none of that should be downloaded to read the landing page or
// to sign in.
const AreaDetailPage = lazy(() =>
  import('./pages/AreaDetailPage').then((module) => ({ default: module.AreaDetailPage })),
)
const DashboardPage = lazy(() =>
  import('./pages/DashboardPage').then((module) => ({ default: module.DashboardPage })),
)
const DivisionsPage = lazy(() =>
  import('./pages/DivisionsPage').then((module) => ({ default: module.DivisionsPage })),
)
const FieldAnalysisPage = lazy(() =>
  import('./pages/FieldAnalysisPage').then((module) => ({ default: module.FieldAnalysisPage })),
)
const FleetPage = lazy(() =>
  import('./pages/FleetPage').then((module) => ({ default: module.FleetPage })),
)
const FlightDetailPage = lazy(() =>
  import('./pages/FlightDetailPage').then((module) => ({ default: module.FlightDetailPage })),
)
const ForgotPasswordPage = lazy(() =>
  import('./pages/ForgotPasswordPage').then((module) => ({ default: module.ForgotPasswordPage })),
)
const LoginPage = lazy(() =>
  import('./pages/LoginPage').then((module) => ({ default: module.LoginPage })),
)
const NewAreaPage = lazy(() =>
  import('./pages/NewAreaPage').then((module) => ({ default: module.NewAreaPage })),
)
const OperationsPage = lazy(() =>
  import('./pages/OperationsPage').then((module) => ({ default: module.OperationsPage })),
)
const RegisterPage = lazy(() =>
  import('./pages/RegisterPage').then((module) => ({ default: module.RegisterPage })),
)
const ResetPasswordPage = lazy(() =>
  import('./pages/ResetPasswordPage').then((module) => ({ default: module.ResetPasswordPage })),
)
const SettingsPage = lazy(() =>
  import('./pages/SettingsPage').then((module) => ({ default: module.SettingsPage })),
)
const VerifyEmailPage = lazy(() =>
  import('./pages/VerifyEmailPage').then((module) => ({ default: module.VerifyEmailPage })),
)

function RouteFallback() {
  return (
    <div className="px-6 py-10">
      <p className="text-sm text-[var(--color-ink-soft)]">Loading…</p>
    </div>
  )
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/verify-email" element={<VerifyEmailPage />} />
      <Route
        path="/app"
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="areas/new" element={<NewAreaPage />} />
        <Route path="areas/:id" element={<AreaDetailPage />} />
        <Route path="fields" element={<FieldAnalysisPage />} />
        <Route path="fleet" element={<FleetPage />} />
        <Route path="fleet/:flightId" element={<FlightDetailPage />} />
        <Route path="operations" element={<OperationsPage />} />
        <Route path="divisions" element={<DivisionsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<RouteFallback />}>
            <AppRoutes />
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
