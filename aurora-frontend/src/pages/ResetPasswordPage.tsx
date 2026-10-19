import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { AuthShell, NightLink } from '../components/AuthShell'
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
      <AuthShell
        eyebrow="Password reset"
        title="Invalid reset link"
        aside={<NightLink to="/forgot-password">Request a new link</NightLink>}
      >
        <p className="text-sm leading-relaxed text-mist">
          This link is missing its reset token. Request a new one below.
        </p>
      </AuthShell>
    )
  }

  // An arrow defined after the guard rather than a hoisted declaration:
  // TypeScript analyses a function declaration as if it were created at the
  // top of the scope, where `token` has not been narrowed to a string yet.
  const handleSubmit = async (event: FormEvent) => {
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
      await api.confirmPasswordReset(token, password)
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
    <AuthShell
      eyebrow="Password reset"
      title="Set a new password"
      blurb="This resets your password everywhere you're currently signed in."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <PasswordField
          id="password"
          label="New password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          required
          minLength={8}
        />
        <PasswordField
          id="confirmPassword"
          label="Confirm new password"
          value={confirmPassword}
          onChange={setConfirmPassword}
          autoComplete="new-password"
          required
          minLength={8}
        />

        {error && <p className="night-alert px-3.5 py-2.5 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="btn btn-acid w-full px-4 py-2.5 text-sm"
        >
          {submitting ? 'Resetting…' : 'Reset password'}
        </button>
      </form>
    </AuthShell>
  )
}
