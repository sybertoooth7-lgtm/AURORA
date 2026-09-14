import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * Top-level fallback so a runtime error in any page shows a recoverable
 * screen instead of a blank white page. This is deliberately the only
 * error boundary in the app -- one at the root is enough to guarantee
 * something reasonable always renders; per-page boundaries can be added
 * later if a specific page needs to keep working around a failure in a
 * sibling section of itself.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('Unhandled error in AURORA UI:', error, info.componentStack)
  }

  handleReload = () => {
    this.setState({ error: null })
    window.location.assign('/')
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="flex h-full items-center justify-center px-4">
        <div className="w-full max-w-sm text-center">
          <h1 className="font-[var(--font-display)] text-2xl font-semibold">
            Something went wrong
          </h1>
          <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
            The page hit an unexpected error. Your data is safe -- try reloading.
          </p>
          <button
            type="button"
            onClick={this.handleReload}
            className="mt-6 rounded-sm bg-[var(--color-orbit)] px-4 py-2 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90"
          >
            Reload AURORA
          </button>
        </div>
      </div>
    )
  }
}
