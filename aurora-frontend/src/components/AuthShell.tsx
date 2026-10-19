import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { EarthLimb } from './EarthLimb'

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

      {/* A still render rather than the live globe: nothing on this page is
          plotted, so a horizon does not need WebGL -- and the page no longer
          has to load the three.js chunk to draw one. The two scrims are what
          keep the card legible over it. */}
      <div aria-hidden className="pointer-events-none absolute inset-0">
        <EarthLimb position="50% 30%" />
        <div className="absolute inset-0 bg-[rgba(5,7,12,0.46)]" />
        <div className="absolute inset-0 bg-[radial-gradient(85%_70%_at_50%_108%,transparent_18%,rgba(5,7,12,0.88)_68%)]" />
      </div>

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
