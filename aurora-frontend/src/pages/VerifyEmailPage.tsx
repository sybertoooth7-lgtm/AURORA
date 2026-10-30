import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { AuthShell } from '../components/AuthShell'
import { ApiError, api } from '../lib/api'

type Status = 'verifying' | 'success' | 'error'

// The token is single-use. React StrictMode runs effects twice in development,
// and a second confirm would spend an already-consumed token and report a
// failure after the first request succeeded. Cache the in-flight promise per
// token so every mount observes the same outcome.
const confirmations = new Map<string, Promise<void>>()

function confirmOnce(token: string): Promise<void> {
  let pending = confirmations.get(token)
  if (!pending) {
    pending = api.confirmEmailVerification(token)
    confirmations.set(token, pending)
  }
  return pending
}

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
    confirmOnce(token)
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
    <AuthShell
      eyebrow="Email verification"
      title={
        status === 'verifying'
          ? 'Verifying…'
          : status === 'success'
            ? 'Email verified'
            : "Couldn't verify this link"
      }
    >
      {status === 'verifying' && <p className="text-sm text-mist">One moment.</p>}

      {status === 'success' && (
        <>
          <p className="text-sm leading-relaxed text-mist">
            Thanks for confirming your email address.
          </p>
          <Link to="/app" className="btn btn-acid mt-7 px-5 py-2.5 text-sm">
            Go to dashboard
          </Link>
        </>
      )}

      {status === 'error' && (
        <>
          <p className="text-sm leading-relaxed text-mist">
            {error} It may have expired — you can request a new one from the dashboard once you're
            signed in.
          </p>
          <Link to="/app" className="btn btn-ghost mt-7 px-5 py-2.5 text-sm">
            Go to dashboard
          </Link>
        </>
      )}
    </AuthShell>
  )
}
