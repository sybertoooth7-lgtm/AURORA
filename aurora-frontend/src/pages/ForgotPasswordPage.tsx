import { useState, type FormEvent } from 'react'
import { AuthShell, Field, NightLink } from '../components/AuthShell'
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
      <AuthShell
        eyebrow="Password reset"
        title="Check your email"
        aside={<NightLink to="/login">Back to sign in</NightLink>}
      >
        <p className="text-sm leading-relaxed text-mist">
          If an account exists for <span className="text-snow">{email}</span>, we've sent a link to
          reset your password. It expires in an hour.
        </p>
      </AuthShell>
    )
  }

  return (
    <AuthShell
      eyebrow="Password reset"
      title="Reset your password"
      blurb="Enter your email and we'll send you a reset link."
      aside={<NightLink to="/login">Back to sign in</NightLink>}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          id="email"
          label="Email"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
          required
        />

        {error && <p className="night-alert px-3.5 py-2.5 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="btn btn-acid w-full px-4 py-2.5 text-sm"
        >
          {submitting ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
    </AuthShell>
  )
}
