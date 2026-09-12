import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api } from '../lib/api'

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await api.requestPasswordReset(email)
      // Always show the same confirmation, whether or not the email is
      // registered -- the backend responds identically either way so this
      // page can't be used to check who has an account.
      setSubmitted(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="flex h-full items-center justify-center px-4">
        <div className="w-full max-w-sm text-center">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold">Check your email</h1>
          <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
            If an account exists for {email}, we've sent a link to reset your password. It expires
            in an hour.
          </p>
          <Link
            to="/login"
            className="mt-6 inline-block text-sm text-[var(--color-orbit)] underline underline-offset-2"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="font-[var(--font-display)] text-2xl font-semibold">Reset your password</h1>
        <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
          Enter your email and we'll send you a reset link.
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </div>

          {error && <p className="text-sm text-[var(--color-critical)]">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-sm bg-[var(--color-orbit)] px-3 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {submitting ? 'Sending…' : 'Send reset link'}
          </button>
        </form>

        <p className="mt-6 text-sm text-[var(--color-ink-soft)]">
          <Link to="/login" className="text-[var(--color-orbit)] underline underline-offset-2">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
