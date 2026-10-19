import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { AuthShell, Field, NightLink } from '../components/AuthShell'
import { PasswordField } from '../components/PasswordField'
import { ApiError, consumeSessionExpiredFlag } from '../lib/api'
import { useAuth } from '../lib/auth'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const justReset = Boolean((location.state as { passwordReset?: boolean } | null)?.passwordReset)
  // Read once on first render, not on every render -- this also clears
  // the flag, so refreshing the login page afterward doesn't keep
  // reshowing the banner.
  const [sessionExpired] = useState(() => consumeSessionExpiredFlag())
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/app')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Operator access"
      title="Sign in"
      blurb="The pass has already flown over your area. Pick up what it saw."
      aside={
        <>
          No account? <NightLink to="/register">Create one</NightLink>
        </>
      }
    >
      {justReset && (
        <p className="night-ok mb-4 px-3.5 py-2.5 text-sm">
          Password reset. Sign in with your new password.
        </p>
      )}
      {sessionExpired && (
        <p className="night-alert mb-4 px-3.5 py-2.5 text-sm">
          Your session ended. Sign in again to continue.
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          id="username"
          label="Username"
          value={username}
          onChange={setUsername}
          autoComplete="username"
          required
        />
        <PasswordField
          id="password"
          label="Password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          required
          labelAddon={
            <Link
              to="/forgot-password"
              className="text-xs text-mist underline underline-offset-2 transition-colors hover:text-snow"
            >
              Forgot password?
            </Link>
          }
        />

        {error && <p className="night-alert px-3.5 py-2.5 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="btn btn-acid w-full px-4 py-2.5 text-sm"
        >
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthShell>
  )
}
