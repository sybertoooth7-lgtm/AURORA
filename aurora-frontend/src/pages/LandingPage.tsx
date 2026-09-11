import { Link } from 'react-router-dom'

const CHECK_TYPES = [
  {
    title: 'Vegetation stress',
    body: 'NDVI computed from the latest cloud-free Sentinel-2 pass over your fields, with a change score against the trailing baseline.',
  },
  {
    title: 'Land change',
    body: 'Track what changed on a parcel between passes -- clearing, new construction, flooding.',
  },
  {
    title: 'Water monitoring',
    body: 'Watch reservoirs, dams, and irrigation catchments for coverage change over time.',
  },
  {
    title: 'Infrastructure change',
    body: 'Keep an eye on a site or corridor without sending someone to walk it.',
  },
]

const STEPS = [
  {
    n: '01',
    title: 'Mark an area',
    body: 'Click a point on the map and set a radius -- a farm block, a quarry, a catchment.',
  },
  {
    n: '02',
    title: 'AURORA checks the latest pass',
    body: 'We pull the most recent cloud-free Sentinel-2 imagery over that area from the Copernicus Data Space Ecosystem.',
  },
  {
    n: '03',
    title: 'Get a reading, not a picture',
    body: 'NDVI, a change score against the trailing baseline, and an alert if something crossed a threshold worth knowing about.',
  },
]

export function LandingPage() {
  return (
    <div className="min-h-full">
      <header className="border-b border-[var(--color-border)] px-6 py-5">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <span className="font-[var(--font-display)] text-lg font-semibold tracking-tight">
            AURORA
          </span>
          <nav className="flex items-center gap-6 text-sm">
            <Link to="/login" className="text-[var(--color-ink-soft)] hover:text-[var(--color-ink)]">
              Sign in
            </Link>
            <Link
              to="/register"
              className="rounded-sm bg-[var(--color-orbit)] px-4 py-2 font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90"
            >
              Get started
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-3xl px-6 py-20 text-center">
          <h1 className="font-[var(--font-display)] text-4xl font-semibold leading-tight sm:text-5xl">
            Know what changed on your land, before you drive out to look.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-lg text-[var(--color-ink-soft)]">
            AURORA checks any area against the latest satellite pass and tells you what's
            different -- vegetation stress, land change, water coverage -- so the first sign of
            trouble doesn't have to be a phone call.
          </p>
          <div className="mt-8 flex items-center justify-center gap-4">
            <Link
              to="/register"
              className="rounded-sm bg-[var(--color-orbit)] px-5 py-3 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90"
            >
              Start monitoring an area
            </Link>
            <Link
              to="/login"
              className="text-sm text-[var(--color-ink-soft)] underline decoration-[var(--color-border)] underline-offset-4 hover:text-[var(--color-ink)]"
            >
              Sign in
            </Link>
          </div>
        </section>

        <section className="border-t border-[var(--color-border)] bg-[var(--color-paper-raised)] px-6 py-16">
          <div className="mx-auto max-w-5xl">
            <h2 className="font-[var(--font-display)] text-2xl font-semibold">How it works</h2>
            <div className="mt-8 grid gap-8 sm:grid-cols-3">
              {STEPS.map((step) => (
                <div key={step.n}>
                  <p className="font-tabular text-sm text-[var(--color-orbit)]">{step.n}</p>
                  <h3 className="mt-2 font-medium">{step.title}</h3>
                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="px-6 py-16">
          <div className="mx-auto max-w-5xl">
            <h2 className="font-[var(--font-display)] text-2xl font-semibold">What AURORA checks for</h2>
            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              {CHECK_TYPES.map((item) => (
                <div
                  key={item.title}
                  className="rounded-sm border border-[var(--color-border)] p-5"
                >
                  <h3 className="font-medium">{item.title}</h3>
                  <p className="mt-1 text-sm text-[var(--color-ink-soft)]">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-[var(--color-border)] bg-[var(--color-paper-raised)] px-6 py-16">
          <div className="mx-auto max-w-3xl text-center">
            <h2 className="font-[var(--font-display)] text-2xl font-semibold">
              Built on real Sentinel-2 data
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-[var(--color-ink-soft)]">
              AURORA reads directly from the Copernicus Data Space Ecosystem -- the same
              Sentinel-2 archive used by researchers and agencies -- and reports cloud-masked
              NDVI over the exact area you define, not a generic regional estimate.
            </p>
          </div>
        </section>

        <section className="px-6 py-16">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-[var(--font-display)] text-2xl font-semibold">
              Add your first area in under a minute
            </h2>
            <p className="mt-3 text-sm text-[var(--color-ink-soft)]">
              No credit card, no site visit. Click a point on the map and see what the latest
              pass shows.
            </p>
            <Link
              to="/register"
              className="mt-6 inline-block rounded-sm bg-[var(--color-orbit)] px-5 py-3 text-sm font-medium text-[var(--color-paper)] transition-opacity hover:opacity-90"
            >
              Create your account
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--color-border)] px-6 py-8">
        <div className="mx-auto flex max-w-5xl items-center justify-between text-sm text-[var(--color-ink-soft)]">
          <span>AURORA -- Space Intelligence, Nairobi</span>
          <span className="font-tabular">Sentinel-2 / Copernicus Data Space Ecosystem</span>
        </div>
      </footer>
    </div>
  )
}
