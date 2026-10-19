import { useEffect, useRef, useState, type ReactNode } from 'react'

interface RevealProps {
  children: ReactNode
  className?: string
  /** Stagger a row of reveals by giving each one a later delay. */
  delay?: number
}

/**
 * Fades its children up the first time they scroll into view.
 *
 * The observer disconnects after the first hit because a reveal that replays
 * every time you scroll past it stops being an entrance and becomes a
 * distraction. With no IntersectionObserver, or under a reduced-motion
 * setting, the CSS in index.css leaves the content where it was written.
 */
export function Reveal({ children, className = '', delay = 0 }: RevealProps) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    const host = hostRef.current
    if (!host || typeof IntersectionObserver === 'undefined') {
      setShown(true)
      return
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShown(true)
          observer.disconnect()
        }
      },
      { threshold: 0.08, rootMargin: '0px 0px -10% 0px' },
    )
    observer.observe(host)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={hostRef}
      className={`reveal ${shown ? 'is-in' : ''} ${className}`}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  )
}
