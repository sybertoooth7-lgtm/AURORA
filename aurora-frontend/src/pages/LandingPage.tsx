import { Link } from 'react-router-dom'
import { EarthLimb } from '../components/EarthLimb'
import { Reveal } from '../components/Reveal'

const CAPABILITIES = [
  { k: '10 m', v: 'the resolution NDVI is actually computed at, from the red and near-infrared bands' },
  { k: '5 days', v: 'Sentinel-2 revisit over the same point on the ground, cloud permitting' },
  { k: 'Cloud-masked', v: 'the scene classification layer decides which pixels count, not a guess' },
  { k: 'Any area', v: 'mark a point, set a radius. No shapefile, no sensor install, no site visit' },
]

const STEPS = [
  {
    n: '01',
    title: 'Mark an area',
    body: 'Click a point on the globe and set a radius — a farm block, a quarry, a catchment.',
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

const CHECK_TYPES = [
  {
    title: 'Vegetation stress',
    body: 'NDVI computed from the latest cloud-free Sentinel-2 pass over your fields, with a change score against the trailing baseline.',
  },
  {
    title: 'Land change',
    body: 'Track what changed on a parcel between passes — clearing, new construction, flooding.',
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

const NAV = [
  { href: '#capabilities', label: 'Capabilities' },
  { href: '#how', label: 'How it works' },
  { href: '#checks', label: 'What we check' },
  { href: '#divisions', label: 'Divisions' },
]

export function LandingPage() {
  return (
    <div className="night min-h-full">
      <div className="grain" />

      {/* One floating bar rather than a bare nav: the wordmark, the section
          links and the CTA all live inside the same pill, so nothing sits
          directly on the content as it scrolls underneath. */}
      <header className="sticky top-0 z-20 px-4 py-4 sm:px-6">
        <div className="pill-nav mx-auto max-w-6xl justify-between">
          <Link to="/" className="flex items-center gap-2.5 text-snow">
            <span aria-hidden className="h-2.5 w-2.5 rounded-full bg-[var(--color-acid)] shadow-[0_0_14px_rgba(201,242,78,0.8)]" />
            <span className="font-[var(--font-display)] text-base font-semibold tracking-[0.22em]">
              AURORA
            </span>
          </Link>

          <nav className="hidden lg:block" aria-label="Sections">
            {NAV.map((item) => (
              <a key={item.href} href={item.href}>
                {item.label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="hidden px-3 py-2 text-sm text-mist transition-colors hover:text-snow sm:block"
            >
              Sign in
            </Link>
            <Link to="/register" className="btn btn-acid px-4 py-2 text-sm">
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* The planet is the page. The copy sits in the shade of it, the way
            it does in the product: you are reading a report about a place,
            and the place should be visible while you read. */}
        <section className="relative -mt-[4.5rem] flex min-h-[92vh] items-end overflow-hidden pt-[4.5rem]">
          {/* The planet fills the frame and the copy sits in its shade. Full
              bleed rather than a right-hand panel: at this aspect the whole
              width of the render fits without cropping, so the limb arc keeps
              its shape instead of being sliced by a box edge. */}
          <div aria-hidden className="pointer-events-none absolute inset-0">
            <EarthLimb position="50% 26%" />
          </div>
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_right,var(--color-night)_6%,rgba(5,7,12,0.72)_38%,rgba(5,7,12,0.15)_68%,transparent_100%)]"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3 bg-[linear-gradient(to_top,var(--color-night)_12%,rgba(5,7,12,0.65)_48%,transparent_100%)]"
          />

          <div className="relative z-20 mx-auto w-full max-w-6xl px-6 pb-16 sm:pb-24">
            <p className="eyebrow text-mist">Earth observation · Nairobi</p>
            <h1 className="mt-5 max-w-3xl font-[var(--font-display)] text-[2.6rem] leading-[1.02] font-semibold tracking-[-0.035em] text-snow sm:text-6xl lg:text-[4.25rem]">
              Know what changed on your land, before you drive out to look.
            </h1>
            <p className="mt-6 max-w-md text-[0.9375rem] leading-relaxed text-mist">
              AURORA checks any area against the latest satellite pass and tells you what's
              different — vegetation stress, land change, water coverage — so the first sign of
              trouble doesn't have to be a phone call.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link to="/register" className="btn btn-acid px-6 py-3 text-sm">
                Start monitoring an area
              </Link>
              <Link to="/login" className="btn btn-ghost px-6 py-3 text-sm">
                Sign in
              </Link>
            </div>
            <p className="font-tabular mt-14 text-[0.65rem] tracking-[0.18em] text-mist-dim uppercase">
              Illustrative rendering · not survey data
            </p>
          </div>
        </section>

        <section id="capabilities" className="relative border-t border-hairline px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <div className="grid gap-x-10 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
              {CAPABILITIES.map((item, index) => (
                <Reveal key={item.k} delay={index * 90}>
                  <p className="font-[var(--font-display)] text-3xl font-semibold tracking-[-0.03em] text-acid">
                    {item.k}
                  </p>
                  <p className="mt-3 text-sm leading-relaxed text-mist">{item.v}</p>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="how" className="px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <Reveal>
              <h2 className="font-[var(--font-display)] text-4xl font-semibold tracking-[-0.03em] text-snow sm:text-5xl">
                Three clicks, then it runs on a schedule.
              </h2>
            </Reveal>
            <div className="mt-12 grid gap-5 lg:grid-cols-3">
              {STEPS.map((step, index) => (
                <Reveal key={step.n} delay={index * 110}>
                  <div className="glass glass-hover h-full p-7">
                    <p className="font-tabular text-xs tracking-[0.22em] text-mist-dim">{step.n}</p>
                    <h3 className="mt-6 font-[var(--font-display)] text-xl font-semibold tracking-[-0.02em] text-snow">
                      {step.title}
                    </h3>
                    <p className="mt-3 text-sm leading-relaxed text-mist">{step.body}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section id="checks" className="px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <Reveal>
              <h2 className="font-[var(--font-display)] text-4xl font-semibold tracking-[-0.03em] text-snow sm:text-5xl">
                What AURORA checks for
              </h2>
            </Reveal>
            <div className="mt-12 grid gap-5 sm:grid-cols-2">
              {CHECK_TYPES.map((item, index) => (
                <Reveal key={item.title} delay={(index % 2) * 110}>
                  <div className="glass glass-hover h-full p-7">
                    <h3 className="font-[var(--font-display)] text-lg font-semibold text-snow">
                      {item.title}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-mist">{item.body}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* The planning divisions are model output with no hardware behind
            them. Saying so here, on the page that is trying to look
            expensive, is the point of the section. */}
        <section id="divisions" className="px-6 py-20">
          <div className="mx-auto max-w-6xl">
            <Reveal>
              <div className="glass overflow-hidden">
                <div className="grid gap-8 p-8 sm:p-12 lg:grid-cols-[1.1fr_1fr]">
                  <div>
                    <p className="eyebrow text-mist">Also in the console</p>
                    <h2 className="mt-4 font-[var(--font-display)] text-3xl font-semibold tracking-[-0.03em] text-snow sm:text-4xl">
                      Five planning divisions, labelled for what they are
                    </h2>
                    <p className="mt-5 max-w-md text-sm leading-relaxed text-mist">
                      Spacecraft, constellation, mission planning, autonomy and ISRU run in the same
                      account as the imagery. They are architecture and model code — no hardware, no
                      live telemetry — and every response they return carries its provenance, its
                      stage and its limitations in the payload itself.
                    </p>
                  </div>
                  <ul className="grid content-center gap-3">
                    {['Spacecraft design', 'Constellation analysis', 'Mission planning', 'Autonomy & GNC', 'ISRU & resources'].map(
                      (name) => (
                        <li
                          key={name}
                          className="flex items-center justify-between gap-4 rounded-full border border-hairline px-5 py-3 text-sm text-snow"
                        >
                          <span>{name}</span>
                          <span className="font-tabular text-[0.65rem] tracking-[0.16em] text-mist-dim uppercase">
                            Stage 0 · simulated
                          </span>
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        <section className="px-6 py-20">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <h2 className="font-[var(--font-display)] text-4xl font-semibold tracking-[-0.03em] text-snow sm:text-5xl">
                Built on real Sentinel-2 data
              </h2>
              <p className="mx-auto mt-5 max-w-xl text-sm leading-relaxed text-mist">
                AURORA reads directly from the Copernicus Data Space Ecosystem — the same
                Sentinel-2 archive used by researchers and agencies — and reports cloud-masked NDVI
                over the exact area you define, not a generic regional estimate.
              </p>
              <p className="font-tabular mt-6 text-[0.65rem] tracking-[0.18em] text-mist-dim uppercase">
                Copernicus Data Space Ecosystem · Sentinel-2 L2A
              </p>
            </Reveal>
          </div>
        </section>

        <section className="relative overflow-hidden px-6 py-28">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-x-0 top-0 h-full bg-[radial-gradient(60%_70%_at_50%_120%,rgba(201,242,78,0.1)_0%,transparent_65%)]"
          />
          <div className="relative mx-auto max-w-2xl text-center">
            <Reveal>
              <h2 className="font-[var(--font-display)] text-4xl font-semibold tracking-[-0.035em] text-snow sm:text-[3.25rem] sm:leading-[1.05]">
                Add your first area in under a minute.
              </h2>
              <p className="mt-5 text-sm leading-relaxed text-mist">
                No credit card, no site visit. Click a point on the globe and see what the latest
                pass shows.
              </p>
              <Link to="/register" className="btn btn-acid mt-9 px-7 py-3.5 text-sm">
                Create your account
              </Link>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="border-t border-hairline px-6 py-10">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 text-sm text-mist-dim sm:flex-row sm:items-center sm:justify-between">
          <span>AURORA — Space Intelligence, Nairobi</span>
          <span className="font-tabular text-[0.7rem]">Sentinel-2 / Copernicus Data Space Ecosystem</span>
        </div>
      </footer>
    </div>
  )
}
