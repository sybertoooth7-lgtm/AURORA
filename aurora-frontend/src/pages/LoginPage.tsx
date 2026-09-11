import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
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
    <div className="flex h-full items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="font-[var(--font-display)] text-2xl font-semibold">AURORA</h1>
        <p className="mt-1 text-sm text-[var(--color-ink-soft)]">Sign in to your account.</p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium">
              Username
            </label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </div>

          {error && <p className="text-sm text-[var(--color-critical)]">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-sm bg-[var(--color-orbit)] px-3 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-6 text-sm text-[var(--color-ink-soft)]">
          No account?{' '}
          <Link to="/register" className="text-[var(--color-orbit)] underline underline-offset-2">
            Create one
          </Link>
        </p>
      </div>
    </div>
  )
}
