import { useState, type ReactNode } from 'react'

interface PasswordFieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete: 'current-password' | 'new-password'
  required?: boolean
  minLength?: number
  /** Rendered at the right end of the label row, e.g. the "Forgot password?" link. */
  labelAddon?: ReactNode
}

/**
 * Password input with a show/hide toggle. The toggle is a button of type
 * "button" on purpose -- inside these forms a default (submit) button would
 * sign the user in with half-typed input.
 *
 * It is styled for the night card in AuthShell, which is the only place a
 * password is typed on this site; the input box itself comes from the
 * `.night` rules in index.css.
 */
export function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  required,
  minLength,
  labelAddon,
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false)

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="block text-sm font-medium text-snow">
          {label}
        </label>
        {labelAddon}
      </div>
      <div className="relative mt-1.5">
        <input
          id={id}
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          minLength={minLength}
          autoComplete={autoComplete}
          className="w-full px-3.5 py-2.5 pr-11 text-sm"
        />
        <button
          type="button"
          onClick={() => setVisible((isVisible) => !isVisible)}
          aria-pressed={visible}
          aria-label={visible ? 'Hide password' : 'Show password'}
          title={visible ? 'Hide password' : 'Show password'}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-mist transition-colors hover:text-snow"
        >
          {visible ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </div>
    </div>
  )
}

const ICON = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
} as const

function EyeIcon() {
  return (
    <svg {...ICON}>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function EyeOffIcon() {
  return (
    <svg {...ICON}>
      <path d="M3 3l18 18" />
      <path d="M10.7 5.2A10 10 0 0 1 12 5c6.4 0 10 7 10 7a17.5 17.5 0 0 1-3.1 4.1" />
      <path d="M6.4 7.8A17.2 17.2 0 0 0 2 12s3.6 7 10 7a9.8 9.8 0 0 0 4.2-.9" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </svg>
  )
}
