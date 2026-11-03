import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { AssistantReply, AssistantRole, AssistantRoleKey } from '../lib/types'
import { VoxelCore } from './VoxelCore'

/**
 * FRIDAY, the console assistant.
 *
 * The dock is deliberately thin: it renders whatever the backend grounded in
 * the caller's own rows and never invents a figure of its own. The opening
 * message is static copy, not a model greeting. Voice is opt-in and only
 * reads the answer aloud; nothing is sent by microphone.
 *
 * The lens selector picks the role the answer is composed in; each reply also
 * shows the pipeline stages the backend ran so the reasoning is inspectable.
 */

const SUGGESTIONS = [
  'Give me a briefing',
  'Give me an overview',
  'Show my unread alerts',
  "How's the fleet?",
  'Is my data real or simulated?',
  "What's my quota?",
]

// Only used if /assistant/roles cannot be reached; the API is the source of
// truth for the list and its labels.
const FALLBACK_ROLES: AssistantRole[] = [
  { key: 'operator', label: 'Operator', focus: 'fleet, monitoring schedules and readiness' },
  { key: 'agronomist', label: 'Agronomist', focus: 'vegetation, water and climate findings' },
  { key: 'analyst', label: 'Analyst', focus: 'provenance, anomalies and land change' },
  { key: 'responder', label: 'Responder', focus: 'unread alerts and incident areas' },
]

const OPENING =
  "Online. I'm FRIDAY, the console assistant. Pick a lens and ask in plain language — " +
  'I research your areas, alerts, flights and quota live, then show the steps I took.'

interface Turn {
  key: number
  role: 'user' | 'assistant'
  text: string
  reply?: AssistantReply
}

const OPENING_TURN: Turn = { key: 0, role: 'assistant', text: OPENING }

function suggestList(turn: Turn): string[] {
  if (turn.role !== 'assistant') return []
  return turn.reply?.suggestions?.length ? turn.reply.suggestions : SUGGESTIONS
}

function TurnMessage({
  turn,
  onSuggestion,
  showSuggestions,
  anchorRef,
}: {
  turn: Turn
  onSuggestion: (text: string) => void
  showSuggestions: boolean
  anchorRef?: RefObject<HTMLDivElement | null>
}) {
  if (turn.role === 'user') {
    return (
      <p className="ml-auto w-fit max-w-[85%] rounded-[var(--radius-sm)] border border-[rgba(107,180,255,0.35)] bg-[rgba(59,130,246,0.18)] px-3 py-2 text-sm leading-relaxed">
        {turn.text}
      </p>
    )
  }

  return (
    <div
      ref={anchorRef}
      className="max-w-[94%] rounded-[var(--radius-sm)] border border-[rgba(148,170,196,0.16)] bg-[rgba(255,255,255,0.035)] px-3 py-2.5"
    >
      <p className="whitespace-pre-line text-sm leading-relaxed text-[var(--color-snow)]">
        {turn.text}
      </p>

      {turn.reply && turn.reply.facts.length > 0 && (
        <dl className="mt-2.5 grid grid-cols-2 gap-x-3 gap-y-2 border-t border-[rgba(148,170,196,0.14)] pt-2.5">
          {turn.reply.facts.map((fact) => (
            <div key={`${fact.label}-${fact.value}`} className="min-w-0">
              <dt className="truncate font-[var(--font-mono)] text-[0.58rem] tracking-[0.14em] uppercase text-[var(--color-mist-dim)]">
                {fact.label}
              </dt>
              <dd className="font-tabular text-xs leading-snug break-words text-[var(--color-snow)]">
                {fact.value}
              </dd>
            </div>
          ))}
        </dl>
      )}

      {turn.reply && turn.reply.steps.length > 0 && (
        <details className="mt-2.5 border-t border-[rgba(148,170,196,0.14)] pt-2">
          <summary className="cursor-pointer text-[0.58rem] tracking-[0.14em] uppercase text-[var(--color-mist-dim)] hover:text-[var(--color-mist)]">
            Reasoning · {turn.reply.steps.length} steps · {turn.reply.role.label}
            {turn.reply.steps.some((step) => step.status === 'blocked')
              ? ' · check blocked'
              : ''}
          </summary>
          <ol className="mt-2 space-y-1.5">
            {turn.reply.steps.map((step, index) => (
              <li
                key={`${step.name}-${index}`}
                className="flex gap-2 text-[0.68rem] leading-snug"
              >
                <span className="mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded-full border border-[rgba(148,170,196,0.28)] font-[var(--font-mono)] text-[0.55rem] text-[var(--color-mist-dim)]">
                  {index + 1}
                </span>
                <span className="min-w-0">
                  <span className="font-[var(--font-mono)] text-[0.58rem] tracking-[0.1em] uppercase text-[var(--color-mist-dim)]">
                    {step.name}
                  </span>{' '}
                  <span
                    className={
                      step.status === 'blocked'
                        ? 'text-[#F0B49E]'
                        : 'text-[var(--color-mist)]'
                    }
                  >
                    {step.detail}
                  </span>
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}

      {turn.reply && turn.reply.links.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1.5 border-t border-[rgba(148,170,196,0.14)] pt-2">
          {turn.reply.links.map((link) => (
            <Link
              key={`${link.href}-${link.label}`}
              to={link.href}
              className="text-xs text-[#9CCBFF] underline decoration-[rgba(156,203,255,0.45)] underline-offset-2 hover:text-[#CFE6FF]"
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}

      {showSuggestions && suggestList(turn).length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {suggestList(turn).map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onSuggestion(suggestion)}
              className="rounded-full border border-[rgba(107,180,255,0.3)] px-2.5 py-1 text-[0.7rem] text-[var(--color-mist)] hover:border-[rgba(107,180,255,0.65)] hover:text-[var(--color-snow)]"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function AssistantDock() {
  const [open, setOpen] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([OPENING_TURN])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [voice, setVoice] = useState(false)
  const [role, setRole] = useState<AssistantRoleKey>('operator')
  const [roles, setRoles] = useState<AssistantRole[]>(FALLBACK_ROLES)

  const nextKey = useRef(1)
  const scrollRef = useRef<HTMLDivElement>(null)
  const lastAssistantRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const voiceRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    api
      .assistantRoles()
      .then((body) => {
        if (!cancelled) setRoles(body.roles)
      })
      .catch(() => {
        // Keep the built-in list; the backend still validates the key it gets.
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    voiceRef.current = voice
    if (!voice && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
  }, [voice])

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const speak = useCallback((text: string) => {
    if (!voiceRef.current) return
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text.replace(/[•]/g, ','))
    utterance.rate = 1.02
    utterance.pitch = 0.95
    window.speechSynthesis.speak(utterance)
  }, [])

  const send = useCallback(
    async (raw?: string) => {
      const message = (raw ?? draft).trim()
      if (!message || pending) return
      setDraft('')
      setError(null)
      setTurns((previous) => [
        ...previous,
        { key: nextKey.current++, role: 'user', text: message },
      ])
      setPending(true)
      try {
        const reply = await api.askAssistant(message, role)
        setTurns((previous) => [
          ...previous,
          { key: nextKey.current++, role: 'assistant', text: reply.answer, reply },
        ])
        speak(reply.answer)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'The assistant could not be reached.')
      } finally {
        setPending(false)
      }
    },
    [draft, pending, role, speak],
  )

  // When a new reply lands, show it from its first line rather than pinning
  // the view to the bottom of a tall answer; pending/typing still follows the
  // bottom so the indicator is visible.
  useEffect(() => {
    const host = scrollRef.current
    if (!host) return
    if (!pending && !error) {
      const anchor = lastAssistantRef.current
      if (anchor) {
        host.scrollTop = anchor.offsetTop - host.offsetTop - 6
        return
      }
    }
    host.scrollTop = host.scrollHeight
  }, [turns, pending, error])

  useEffect(() => {
    if (!open) return
    const frame = window.setTimeout(() => {
      inputRef.current?.focus()
      // The panel mounts closed, so scrollTop starts at 0; reopening should
      // resume at the newest answer, not replay the whole transcript.
      const host = scrollRef.current
      const anchor = lastAssistantRef.current
      if (host) {
        host.scrollTop = anchor ? anchor.offsetTop - host.offsetTop - 6 : host.scrollHeight
      }
    }, 40)
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(frame)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  const activeRole = useMemo(
    () => roles.find((entry) => entry.key === role) ?? FALLBACK_ROLES[0],
    [roles, role],
  )
  const lastUserMessage = useMemo(
    () => [...turns].reverse().find((turn) => turn.role === 'user')?.text ?? '',
    [turns],
  )
  const lastAssistantIndex = turns.reduce(
    (last, turn, index) => (turn.role === 'assistant' ? index : last),
    -1,
  )

  return (
    // Leaflet's panes and controls sit at z-index 400-800 in the root
    // stacking context, so the dock has to clear them to stay on top of maps.
    <div className="fixed bottom-5 right-5 z-[1200] flex flex-col items-end gap-3">
      {open && (
        <section
          aria-label="FRIDAY assistant"
          className="assistant-surface assistant-panel flex h-[min(34rem,calc(100dvh-7rem))] w-[min(24rem,calc(100vw-2.5rem))] flex-col overflow-hidden rounded-[var(--radius-md)] border border-[rgba(107,180,255,0.28)] bg-[var(--color-night-raised)] text-[var(--color-snow)] shadow-[0_30px_80px_-30px_rgba(5,7,12,0.95)]"
        >
          <header className="flex items-center gap-3 border-b border-[rgba(148,170,196,0.16)] px-3.5 py-2.5">
            <VoxelCore size={42} />
            <div className="min-w-0 flex-1">
              <h2 className="font-[var(--font-display)] text-sm font-semibold tracking-[0.16em]">
                FRIDAY
              </h2>
              <p className="flex items-center gap-1.5 text-[0.62rem] tracking-[0.16em] uppercase text-[var(--color-mist-dim)]">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#7CC6FF] shadow-[0_0_8px_rgba(124,198,255,0.9)]" />
                Grounded · read-only
              </p>
            </div>
            <button
              type="button"
              aria-pressed={voice}
              onClick={() => setVoice((current) => !current)}
              className={`rounded-full border px-2 py-1 text-[0.62rem] tracking-[0.12em] uppercase ${
                voice
                  ? 'border-[rgba(124,198,255,0.65)] bg-[rgba(59,130,246,0.2)] text-[#CFE6FF]'
                  : 'border-[rgba(148,170,196,0.28)] text-[var(--color-mist-dim)] hover:text-[var(--color-mist)]'
              }`}
            >
              Voice {voice ? 'on' : 'off'}
            </button>
            <button
              type="button"
              aria-label="Close assistant"
              onClick={() => setOpen(false)}
              className="grid h-7 w-7 place-items-center rounded-full border border-[rgba(148,170,196,0.22)] text-[var(--color-mist)] hover:border-[rgba(148,170,196,0.5)] hover:text-[var(--color-snow)]"
            >
              ×
            </button>
          </header>

          <div className="flex items-center gap-2 border-b border-[rgba(148,170,196,0.12)] bg-[rgba(255,255,255,0.02)] px-3.5 py-1.5">
            <label
              htmlFor="friday-lens"
              className="text-[0.58rem] tracking-[0.16em] uppercase text-[var(--color-mist-dim)]"
            >
              Lens
            </label>
            <select
              id="friday-lens"
              value={role}
              onChange={(event) => setRole(event.target.value as AssistantRoleKey)}
              className="rounded-[3px] border border-[rgba(148,170,196,0.28)] bg-[var(--color-night)] px-1.5 py-0.5 text-xs text-[var(--color-snow)]"
            >
              {roles.map((entry) => (
                <option key={entry.key} value={entry.key}>
                  {entry.label}
                </option>
              ))}
            </select>
            <span
              className="min-w-0 flex-1 truncate text-[0.62rem] text-[var(--color-mist-dim)]"
              title={activeRole?.focus}
            >
              {activeRole?.focus}
            </span>
          </div>

          <div
            ref={scrollRef}
            aria-live="polite"
            className="assistant-scroll flex-1 space-y-3 overflow-y-auto px-3.5 py-3"
          >
            {turns.map((turn, index) => (
              <TurnMessage
                key={turn.key}
                turn={turn}
                onSuggestion={(text) => void send(text)}
                showSuggestions={index === turns.length - 1}
                anchorRef={index === lastAssistantIndex ? lastAssistantRef : undefined}
              />
            ))}

            {pending && (
              <div className="flex w-fit items-center gap-1 rounded-[var(--radius-sm)] border border-[rgba(148,170,196,0.16)] bg-[rgba(255,255,255,0.035)] px-3 py-2.5">
                <span className="assistant-dot h-1.5 w-1.5 rounded-full bg-[#7CC6FF]" />
                <span
                  className="assistant-dot h-1.5 w-1.5 rounded-full bg-[#7CC6FF]"
                  style={{ animationDelay: '0.15s' }}
                />
                <span
                  className="assistant-dot h-1.5 w-1.5 rounded-full bg-[#7CC6FF]"
                  style={{ animationDelay: '0.3s' }}
                />
                <span className="ml-2 text-xs text-[var(--color-mist-dim)]">
                  Reading your account…
                </span>
              </div>
            )}

            {error && (
              <div className="rounded-[var(--radius-sm)] border border-[rgba(181,80,46,0.45)] bg-[rgba(181,80,46,0.12)] px-3 py-2.5 text-xs leading-relaxed text-[#F0B49E]">
                {error}
                {lastUserMessage && (
                  <button
                    type="button"
                    onClick={() => void send(lastUserMessage)}
                    className="ml-2 underline underline-offset-2"
                  >
                    Retry
                  </button>
                )}
              </div>
            )}
          </div>

          <form
            onSubmit={(event) => {
              event.preventDefault()
              void send()
            }}
            className="border-t border-[rgba(148,170,196,0.16)] px-3.5 pt-2.5 pb-2"
          >
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                maxLength={500}
                placeholder="Ask about your areas, alerts, flights…"
                aria-label="Ask FRIDAY"
                className="h-10 min-w-0 flex-1 px-3 text-sm"
              />
              <button
                type="submit"
                disabled={!draft.trim() || pending}
                className="btn h-10 rounded-[var(--radius-sm)] bg-[#2F6BFF] px-4 text-sm font-medium text-white shadow-[0_10px_24px_-12px_rgba(59,130,246,0.9)] hover:bg-[#3B7BFF] disabled:opacity-40"
              >
                Send
              </button>
            </div>
            <p className="mt-1.5 text-[0.58rem] tracking-[0.16em] uppercase text-[var(--color-mist-dim)]">
              Answers come from your account · nothing is changed
            </p>
          </form>
        </section>
      )}

      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open FRIDAY assistant"
          className="flex items-center gap-2.5 rounded-full border border-[rgba(107,180,255,0.4)] bg-[var(--color-night-raised)] py-1.5 pr-4 pl-1.5 text-[var(--color-snow)] shadow-[0_18px_44px_-18px_rgba(5,7,12,0.95)] hover:border-[rgba(107,180,255,0.7)]"
        >
          <VoxelCore size={32} />
          <span className="font-[var(--font-display)] text-xs font-semibold tracking-[0.18em]">
            FRIDAY
          </span>
          <span className="h-1.5 w-1.5 rounded-full bg-[#7CC6FF] shadow-[0_0_8px_rgba(124,198,255,0.9)]" />
        </button>
      )}
    </div>
  )
}
