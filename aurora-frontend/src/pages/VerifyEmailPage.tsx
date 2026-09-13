import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '../lib/api'

type Status = 'verifying' | 'success' | 'error'

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<Status>('verifying')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setError('This link is missing its verification token.')
      return
    }
    let cancelled = false
    api
      .confirmEmailVerification(token)
      .then(() => {
        if (!cancelled) setStatus('success')
      })
      .catch((err) => {
        if (cancelled) return
        setStatus('error')
        setError(
          err instanceof ApiError
            ? err.message
            : 'Something went wrong confirming this link.',
        )
      })
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <div className="flex h-full items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        {status === 'verifying' && (
          <>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold">Verifying…</h1>
            <p className="mt-3 text-sm text-[var(--color-ink-soft)]">One moment.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold">Email verified</h1>
            <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
              Thanks for confirming your email address.
            </p>
            <Link
              to="/app"
              className="mt-6 inline-block rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90"
            >
              Go to dashboard
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <h1 className="font-[var(--font-display)] text-2xl font-semibold">
              Couldn't verify this link
            </h1>
            <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
              {error} It may have expired -- you can request a new one from the dashboard once
              you're signed in.
            </p>
            <Link
              to="/app"
              className="mt-6 inline-block text-sm text-[var(--color-orbit)] underline underline-offset-2"
            >
              Go to dashboard
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
