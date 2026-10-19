import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { AuthShell, Field, NightLink } from '../components/AuthShell'
import { PasswordField } from '../components/PasswordField'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register({ email, username, password, full_name: fullName || undefined })
      navigate('/app')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create your account. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Start watching an area"
      title="Create your account"
      blurb="No card, no site visit. Mark a point on the globe and the next clear pass gets read."
      aside={
        <>
          Already have an account? <NightLink to="/login">Sign in</NightLink>
        </>
      }
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
        <Field
          id="username"
          label="Username"
          value={username}
          onChange={setUsername}
          autoComplete="username"
          required
        />
        <Field id="fullName" label="Full name (optional)" value={fullName} onChange={setFullName} autoComplete="name" />
        <PasswordField
          id="password"
          label="Password"
          value={password}
          onChange={setPassword}
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
          {submitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
    </AuthShell>
  )
}
