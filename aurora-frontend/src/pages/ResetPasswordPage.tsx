import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { PasswordField } from '../components/PasswordField'
import { ApiError, api } from '../lib/api'

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const navigate = useNavigate()

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (!token) {
    return (
      <div className="flex h-full items-center justify-center px-4">
        <div className="w-full max-w-sm text-center">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold">
            Invalid reset link
          </h1>
          <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
            This link is missing its reset token. Request a new one below.
          </p>
          <Link
            to="/forgot-password"
            className="mt-6 inline-block text-sm text-[var(--color-orbit)] underline underline-offset-2"
          >
            Request a new link
          </Link>
        </div>
      </div>
    )
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)

    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setSubmitting(true)
    try {
      await api.confirmPasswordReset(token as string, password)
      navigate('/login', { state: { passwordReset: true } })
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Something went wrong. Try requesting a new reset link.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="font-[var(--font-display)] text-2xl font-semibold">Set a new password</h1>
        <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
          This resets your password everywhere you're currently signed in.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <PasswordField
              id="password"
              label="New password"
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              required
              minLength={8}
            />
          </div>
          <div>
            <PasswordField
              id="confirmPassword"
              label="Confirm new password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              autoComplete="new-password"
              required
              minLength={8}
            />
          </div>

          {error && <p className="text-sm text-[var(--color-critical)]">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full btn btn-primary px-3 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? 'Resetting…' : 'Reset password'}
          </button>
        </form>
      </div>
    </div>
  )
}
