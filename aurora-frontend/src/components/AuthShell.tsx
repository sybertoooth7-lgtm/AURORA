import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { EarthGlobe, type GlobePoint } from '../components/EarthGlobe'

const NO_POINTS: GlobePoint[] = []

interface AuthShellProps {
  eyebrow?: string
  title: string
  blurb?: string
  children: ReactNode
  /** Anything below the card -- usually the link to the other half of the flow. */
  aside?: ReactNode
}

/**
 * The one screen furniture shared by every page you reach before you have a
 * session: sign in, register, and the three password/email flows.
 *
 * It is deliberately not the console. There is nothing to read here except a
 * form, so the planet is allowed to be the whole background -- a limb rising
 * out of the bottom of the viewport, with the card sitting in front of it.
 */
export function AuthShell({ eyebrow, title, blurb, children, aside }: AuthShellProps) {
  return (
    <div className="night relative flex min-h-full items-center justify-center overflow-hidden px-4 py-16">
      <div className="grain" />

      {/* Decorative: no points, no handlers. The limb is oversized and pushed
          below the fold so what you see is a horizon, not a diagram. */}
      <div aria-hidden className="pointer-events-none absolute inset-x-[-25%] bottom-[-58%] h-[105%]">
        <EarthGlobe
          className="h-full w-full"
          points={NO_POINTS}
          initialAltitude={1.35}
          fallback={<div className="h-full w-full bg-[radial-gradient(80%_60%_at_50%_100%,#16233A_0%,#05070C_70%)]" />}
        />
      </div>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(90%_70%_at_50%_115%,transparent_28%,rgba(5,7,12,0.82)_72%)]"
      />

      <Link
        to="/"
        className="absolute top-6 left-6 z-20 flex items-center gap-2.5 text-snow transition-opacity hover:opacity-80"
      >
        <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-[var(--color-acid)] shadow-[0_0_14px_rgba(201,242,78,0.8)]" />
        <span className="font-[var(--font-display)] text-base font-semibold tracking-[0.22em]">
          AURORA
        </span>
      </Link>

      <div className="glass relative z-20 w-full max-w-md p-8 sm:p-10">
        {eyebrow && <p className="eyebrow text-mist">{eyebrow}</p>}
        <h1 className="font-[var(--font-display)] text-[1.75rem] leading-tight font-semibold tracking-[-0.025em] text-snow">
          {title}
        </h1>
        {blurb && <p className="mt-2 text-sm leading-relaxed text-mist">{blurb}</p>}

        <div className="mt-8">{children}</div>

        {aside && <div className="mt-8 text-sm text-mist">{aside}</div>}
      </div>
    </div>
  )
}

/** The link style used inside the night card, where the paper orbit blue has
    too little contrast against a black field. */
export function NightLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link
      to={to}
      className="text-acid underline decoration-[rgba(201,242,78,0.35)] underline-offset-4 transition-colors hover:decoration-[rgba(201,242,78,0.8)]"
    >
      {children}
    </Link>
  )
}

interface FieldProps {
  id: string
  label: ReactNode
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'email'
  autoComplete?: string
  required?: boolean
}

/**
 * A labelled input on the night side. The box itself comes from the `.night`
 * rules in index.css, so this only carries the layout and the label.
 */
export function Field({
  id,
  label,
  value,
  onChange,
  type = 'text',
  autoComplete,
  required,
}: FieldProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-snow">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        required={required}
        className="mt-1.5 w-full px-3.5 py-2.5 text-sm"
      />
    </div>
  )
}
