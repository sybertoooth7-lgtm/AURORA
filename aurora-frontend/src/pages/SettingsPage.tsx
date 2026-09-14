import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { ApiError, api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { ApiKeyCreated, ApiKeyListEntry } from '../lib/types'

const EXPIRY_OPTIONS: Array<{ days: number | null; label: string }> = [
  { days: null, label: 'Never expires' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
  { days: 365, label: '365 days' },
]

function formatDate(value: string | null): string {
  if (!value) return '—'
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

export function SettingsPage() {
  const { user, refreshProfile } = useAuth()
  const [keys, setKeys] = useState<ApiKeyListEntry[]>([])
  const [created, setCreated] = useState<ApiKeyCreated | null>(null)
  const [createError, setCreateError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [expiry, setExpiry] = useState<string>('never')
  const [copied, setCopied] = useState(false)
  const [resending, setResending] = useState(false)
  const [resendNote, setResendNote] = useState<string | null>(null)

  const refreshKeys = useCallback(() => {
    api
      .listApiKeys()
      .then((data) => setKeys(data.keys))
      .catch(() => {})
  }, [])

  useEffect(() => {
    refreshKeys()
  }, [refreshKeys])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setCreateError(null)
    setCopied(false)
    setCreating(true)
    try {
      const trimmed = name.trim()
      if (!trimmed) {
        setCreateError('Give the key a name so you can recognise it later.')
        return
      }
      const selected = EXPIRY_OPTIONS.find((option) => option.label === expiry) ?? EXPIRY_OPTIONS[0]
      const result = await api.createApiKey({
        name: trimmed,
        ...(selected.days != null ? { expires_days: selected.days } : {}),
      })
      setCreated(result)
      setName('')
      setExpiry('never')
      await refreshKeys()
    } catch (err) {
      setCreateError(err instanceof ApiError ? err.message : 'Could not create the key.')
    } finally {
      setCreating(false)
    }
  }

  async function handleRevoke(id: number) {
    try {
      await api.revokeApiKey(id)
      await refreshKeys()
    } catch {
      // Left alone; the list will refresh on the next successful load.
    }
  }

  async function handleResend() {
    setResending(true)
    setResendNote(null)
    try {
      const { detail } = await api.resendEmailVerification()
      setResendNote(detail)
    } catch (err) {
      setResendNote(err instanceof ApiError ? err.message : 'Could not resend the verification email.')
    } finally {
      setResending(false)
    }
  }

  async function handleCopyCreated() {
    if (!created) return
    try {
      await navigator.clipboard.writeText(created.key)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="font-[var(--font-display)] text-2xl font-semibold">Settings</h1>
      <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
        Your account and the machine credentials used by robots and data pipelines.
      </p>

      <section className="mt-8 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-5 py-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
          Account
        </h2>
        <dl className="mt-4 space-y-3 text-sm">
          <div className="flex items-baseline justify-between">
            <dt className="text-[var(--color-ink-soft)]">Username</dt>
            <dd className="font-medium">{user?.username}</dd>
          </div>
          <div className="flex items-baseline justify-between">
            <dt className="text-[var(--color-ink-soft)]">Email</dt>
            <dd className="font-medium">{user?.email || '—'}</dd>
          </div>
          <div className="flex items-baseline justify-between">
            <dt className="text-[var(--color-ink-soft)]">Email verified</dt>
            <dd>
              {user?.email_verified ? (
                <span className="text-[#4F7942]">Yes</span>
              ) : (
                <span className="flex items-baseline gap-2 text-[var(--color-ink)]">
                  <span className="text-[var(--color-critical)]">No — required for new jobs</span>
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={resending}
                    className="text-sm text-[var(--color-orbit)] underline underline-offset-2 disabled:opacity-50"
                  >
                    {resending ? 'Resending…' : 'Resend confirmation'}
                  </button>
                </span>
              )}
            </dd>
          </div>
        </dl>
        {resendNote && (
          <p className="mt-3 text-sm text-[var(--color-ink-soft)]">{resendNote}</p>
        )}
        <button
          type="button"
          onClick={() => void refreshProfile()}
          className="mt-4 text-sm text-[var(--color-ink-soft)] underline decoration-[var(--color-border)] underline-offset-2 hover:text-[var(--color-ink)]"
        >
          Refresh profile
        </button>
      </section>

      <section className="mt-8 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-5 py-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
          Create an API key
        </h2>
        <p className="mt-2 text-sm text-[var(--color-ink-soft)]">
          Keys authenticate robots, scripts and pipelines with the same{' '}
          <code className="font-mono text-xs">Authorization: Bearer</code> header as a login. The
          secret is shown exactly once.
        </p>
        <form onSubmit={handleCreate} className="mt-4 flex flex-wrap items-end gap-3">
          <label className="block flex-1 text-sm font-medium">
            Name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. fleet-bridge"
              className="mt-1 w-full rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            />
          </label>
          <label className="block text-sm font-medium">
            Expires
            <select
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              className="mt-1 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper)] px-3 py-2 text-sm focus:border-[var(--color-orbit)] focus:outline-none"
            >
              {EXPIRY_OPTIONS.map((option) => (
                <option key={option.label} value={option.label}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={creating}
            className="rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {creating ? 'Creating…' : 'Create key'}
          </button>
        </form>
        {createError && <p className="mt-3 text-sm text-[var(--color-critical)]">{createError}</p>}

        {created && (
          <div className="mt-4 rounded-sm border border-[var(--color-orbit)] bg-[var(--color-paper)] px-4 py-3">
            <p className="text-sm font-medium">Key created — copy it now, it won't be shown again</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <code className="break-all rounded-sm bg-[var(--color-paper-raised)] px-3 py-2 font-mono text-xs">
                {created.key}
              </code>
              <button
                type="button"
                onClick={() => void handleCopyCreated()}
                className="text-sm text-[var(--color-orbit)] underline underline-offset-2"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <p className="mt-2 text-xs text-[var(--color-ink-soft)]">
              Prefix <code className="font-mono">{created.prefix}</code>
              {created.expires_at && (
                <>
                  {' '}· expires {formatDate(created.expires_at)}
                </>
              )}
            </p>
          </div>
        )}
      </section>

      <section className="mt-8 rounded-sm border border-[var(--color-border)] bg-[var(--color-paper-raised)] px-5 py-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--color-ink-soft)]">
          Active keys
        </h2>
        {keys.length === 0 ? (
          <p className="mt-4 text-sm text-[var(--color-ink-soft)]">
            No keys yet. Create one above for a robot, script or pipeline.
          </p>
        ) : (
          <table className="mt-3 w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-ink-soft)]">
                <th className="py-2 font-medium">Name</th>
                <th className="hidden py-2 font-medium sm:table-cell">Prefix</th>
                <th className="hidden py-2 font-medium lg:table-cell">Created</th>
                <th className="py-2 font-medium">Expires</th>
                <th className="hidden py-2 font-medium md:table-cell">Last used</th>
                <th className="py-2 font-medium">Status</th>
                <th className="py-2 font-medium"> </th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} className="border-b border-[var(--color-border)]">
                  <td className="py-2 pr-4 font-medium">{key.name}</td>
                  <td className="font-mono hidden py-2 pr-4 text-xs text-[var(--color-ink-soft)] sm:table-cell">
                    {key.prefix}
                  </td>
                  <td className="font-tabular hidden py-2 pr-4 text-[var(--color-ink-soft)] lg:table-cell">
                    {formatDate(key.created_at)}
                  </td>
                  <td className="font-tabular py-2 pr-4 text-[var(--color-ink-soft)]">
                    {formatDate(key.expires_at)}
                  </td>
                  <td className="font-tabular hidden py-2 pr-4 text-[var(--color-ink-soft)] md:table-cell">
                    {formatDate(key.last_used_at)}
                  </td>
                  <td className="py-2 pr-4">
                    {key.revoked ? (
                      <span className="text-[var(--color-ink-soft)]">Revoked</span>
                    ) : (
                      <span className="text-[#4F7942]">Active</span>
                    )}
                  </td>
                  <td className="py-2 text-right">
                    {!key.revoked && (
                      <button
                        type="button"
                        onClick={() => void handleRevoke(key.id)}
                        className="text-sm text-[var(--color-critical)] underline underline-offset-2"
                      >
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}