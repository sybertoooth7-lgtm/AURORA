# Changelog

All notable changes to the AURORA platform. Dates are when the change landed on `main`.

## Unreleased

0.3.0 "Platform growth" — the account, the queue and the silent divisions: an operator can now read their own history, see why a job did not finish, and reach every division of the company as a planning tool that says so on the page. `APP_VERSION` is already at `0.3.0` so the release number travels with the code; this heading becomes `## [0.3.0]` when the branch merges.

### Added
- **Account roll-up and paged listings** — `GET /analysis/` is filtered and paginated with a real total (a short page no longer looks like a short history), `GET /analysis/summary` reports quota headroom and the real-vs-simulated provenance split, each area gained a monitoring time series across passes, and bulk field-boundary import reserves quota for the whole batch before spending any of it.
- **API keys** (`/auth/api-keys`) — mint/list/revoke machine credentials with the same bearer header as JWTs (`app/api_keys.py`, `app/models/api_key.py`, migration `3b7e9f1c2d5a`). Secrets are `aur_`-prefixed, SHA-256-hashed at rest, shown once at creation, revocable and optionally expiring; `get_current_user` routes by prefix before it ever hits the DB.
- **Email verification is now enforced** — capability-gated endpoints (new analyses, AI inference, insurance checks, robotics inspect/simulate, onboarding first-analysis) return `403 email_unverified` until the address is confirmed (`VerificationRequiredError`, `require_verified`); reads and the verification flow stay open. `GET /auth/me` exposes the profile (incl. `email_verified`) and the onboarding checklist gained an `email_verified` step.
- **Operator CLI** (`backend/cli.py`) — first-admin bootstrap and account administration without a second API route: `create-admin`, `set-admin`, `revoke-admin`, `list-users`, `set-verified`; password via `AURORA_CLI_PASSWORD` or an interactive prompt; bootstrap emails gated by `CLI_ADMIN_EMAIL_DOMAIN`.
- **Fleet dashboard API** — `GET /robotics/flights` (all flights, newest first), `GET /robotics/flights/{id}/telemetry` (paginated frames), `POST /robotics/simulate` (deterministic orbit survey openly labelled `is_simulated`) for the operations-fleet UI.
- **Web UI** — operations fleet page with flight health/KPIs, flight detail page with inline-SVG telemetry charts (battery, altitude, motor temp, GPS accuracy), post-flight satellite inspection panel, and a Settings page with account verification status + full API-key management (create with one-time secret reveal, list, revoke).
- **Field-boundary crop analysis** (`POST /crop/analyze`, tag "Crop Analysis") — end-to-end: accepts a GeoJSON field polygon (single closed ring, 3–250 vertices), derives the survey area (centroid + covering radius, `boundary_wkt` in `app/routes/crop.py`), fetches the latest satellite observation, measures NDVI through the `vegetation` pipeline, persists the run as a normal completed analysis/result/alerts, and returns a structured report (`app/schemas/crop.py`) with the observation, NDVI/condition, metrics, model identity, and `report` lines. Provenance is explicit (`real` vs `simulated`); boundary validation rejects unclosed/degenerate/out-of-range rings.
- **The five silent divisions are now reachable** — spacecraft, constellation, multi-planetary, space-resources and mission planning had architecture and model code but no HTTP surface. 17 authenticated endpoints (`app/routes/spacecraft.py`, `space_division.py`, `multiplanetary.py`, `space_resources.py`, `mission_planning.py`) share one response envelope that carries provenance, stage and the specific limits of the model that produced the number, so a simulated yield cannot be forwarded as a measurement. Two exceptions are deliberate: `/mission-planning/data-readiness` reports the platform's own job outcomes and is flagged `real` with its inference spelled out in `basis`, and command signing is not exposed at all because it HMACs with a built-in default key.
- **One job pipeline instead of four** — every analysis now enters through `enqueue_analysis`, which applies a single timeout/retry/result-TTL policy (`app/queue.py`), and `analysis_runner` classifies failures so known-permanent ones (unknown pipeline, bad input) do not spend further retries. Each retry costs real Sentinel Hub processing units.
- **Observation cache** (`app/cache.py`) — a repeat of the same area reuses a recent observation for `OBSERVATION_CACHE_TTL_SECONDS`, keyed on provider class plus 6dp coordinates, so a simulated entry can never be served for a live provider and neighbouring fields never collide. Cached payloads rebuild through `SatelliteObservation.from_dict`; provenance stays derived from the source id.
- **Job observability** — `app/job_metrics.py` keeps daily counters and a newest-first failure trail, exposed with stuck analysis rows on `GET /system/jobs` (administrators only). Queue counters alone could not tell a broken worker from an idle one. `worker.py` gained `--queue/--burst/--max-jobs/--max-idle` flags and an exception handler.
- **Composite indexes** for the paged list, roll-up and history queries (migration `e2f3a4b5c6d7`). Alembic `upgrade head` is exercised in CI against PostGIS 16; migrations still cannot run on a machine with no database.
- **3D orbital view** (`EarthGlobe.tsx`) — a lit, textured globe with atmosphere that plots the same areas the table lists: the Overview hero, the New-area picker (click the planet, then fine-tune on the survey map), the area detail header at two scales, and the sign-in and landing pages. globe.gl is imported dynamically because three.js is a ~1.9MB chunk the table-only screens should not pay for, and every globe has a fallback so a browser without WebGL keeps the same information. Textures are vendored renders and are labelled as renders, not mission data.
- **Pages for the scaled backend** — divisions page, field-analysis page, and `SimulationPanel` so a provenance badge and the model's own limitations travel with every division number. The dashboard pages through the listing instead of assuming one request returns all areas.
- **Earth as a still, where the planet is scenery** (`EarthLimb.tsx`, `src/assets/earth/limb-render.jpg`) — a lit limb with the sun coming over the horizon, used on the landing hero and behind every pre-session form. It is a rendered *view*, not an equirectangular texture, so it cannot be wrapped onto a sphere and does not try to: the console keeps `EarthGlobe` because that one plots your areas. The public pages no longer import globe.gl at all, which keeps the ~1.9MB three.js chunk off the screens that never needed it.
- **Show/hide toggle on every password field** (`PasswordField.tsx`) — the toggle is a `type="button"` on purpose: a default submit button inside these forms would sign a user in with half-typed input. Edge draws its own reveal glyph inside password inputs, so `::-ms-reveal` is suppressed.

### Changed
- **The arrival surfaces went dark; the console did not.** Landing and everything you see before you hold a session (sign in, register, forgot/reset password, verify e-mail) moved onto a night layer -- a dark glass system with an acid-green accent, the Earth filling the frame behind the copy, and scroll reveals. The signed-in product stays the paper instrument panel: it is where operators read numbers all day, and a dark translucent surface costs legibility there and buys nothing. `PasswordField` was retuned for the card, keeping its `type="button"` toggle behaviour.
- **One visual standard instead of fifteen hand-assembled ones.** Theme tokens retuned (hairline borders, softer radii), shared `panel` / `eyebrow` / `orbital` / `btn*` classes, mono column headers, row and control states, a keyboard focus ring, and reduced-motion handling. Scroll animation is behind `prefers-reduced-motion`, and the night glow, grain and reveals all fall back to a static frame under it.
- Validation responses put 422 reasons under `errors` rather than `detail`, and the client reads them there instead of showing "Request validation failed".
- `AGENTS.md` corrected to the toolchain actually in use (`backend/.venv`, 575 tests, `npm run lint`).

### Fixed
- Reader-facing copy rendered `--` where it should set an em dash (the landing hero, the divisions and Copernicus bands, the footer, the expired-verification notice and the error boundary). Code comments keep the ASCII form on purpose.
- Docs no longer claim API keys are unimplemented or that email verification is informational-only (both now shipped).
- Zero-feedstock extraction returned `infinity` for specific energy (a 500 on JSON encode) and prospecting put occurrence objects where the schema wanted resource names.
- The field-analysis page had an auto-run effect that depended on the state its own response writes, re-firing until the shared 120 req/min throttle cut it off; runs are now mount-scoped and the Run button applies changed inputs.
- `.gitignore`: a blanket `lib/` rule silently hid any new file under `aurora-frontend/src/lib/`, and `.venv/` was not ignored at all.
- `POST /auth/token` with anything other than a JSON body (an OAuth2 form post, a text body) returned a bare `500` with no CORS headers: the unparsed body became the `input` of the validation error, the error could not be serialised, and the failure escaped the exception handler. Validation errors are now sanitised once, shared by the response and the log line, so the caller gets `422 validation_failed` -- and the raw body, which is a credential, is neither echoed to the client nor written to the log.

### Known issues
- `src/assets/earth/limb-render.jpg` came from a supplied wallpaper and its licence is **unverified**. It is labelled as a render wherever it appears, but it should be cleared or swapped for a real NASA Blue Marble / Black Marble frame before this is put in front of a customer.
- Two tracked files in `backend/app/mission_planning/` have mangled names (`init · PY`, a 2-byte file, and a duplicate `Readme · MD`). Harmless to the suite, left in place rather than deleted.

### Planned
- Deploy Sentinel-2 credentials (`SENTINEL_CLIENT_ID` / `SENTINEL_CLIENT_SECRET`) to production (with `ENABLE_DEMO_MODE=false` and PostGIS + Redis provisioned).

## [0.2.0] - 2026-09-11 — AURORA-2 "Earth-revenue integration"

Earth-revenue subsystems on top of the AURORA-1 intelligence platform, plus the first fully-green CI.

### Added
- **Parametric agriculture insurance** — `GET /insurance/defaults` + `POST /insurance/trigger-check` (`app/services/insurance.py`), `insurance_index` pipeline, pure trigger/payout evaluation. Payouts are estimates, never settlements.
- **Robotics field services** — drone/ground-robot telemetry bridge (`POST /robotics/flights/{id}/telemetry`, in-memory flight store in `app/robotics/flight.py`), flight health summariser, satellite NDVI damage inspection fused with flight health (`POST /robotics/inspect`), `robotics_inspection` pipeline.
- **User onboarding** — `GET /onboarding/status`, `POST /onboarding/complete`, `POST /onboarding/first-analysis`, honest simulated-vs-real disclosure at each step.
- **CI pipeline** (GitHub Actions) — backend gates (ruff, mypy, Alembic `upgrade head` against PostGIS 16, full pytest incl. Redis auth-hardening) and frontend build.
- Pinned dev toolchain in `backend/requirements-dev.txt` (`ruff==0.16.7`, `mypy==2.3.1`).

### Fixed
- CI never ran: `postgis/postgis:16-3.3` has no manifest on Docker Hub → pinned `16-3.5` in the workflow and `docker-compose.yml`.
- Ruff/type parity between local and CI (pinned toolchain; two single-element `isinstance` tuples → plain class checks).
- Frontend CI off EOL Node 20 → Node 24 LTS.

## [0.1.0] — 2026 Q3 — AURORA-1 "Space Intelligence Platform" foundation

The platform base (predates the current versioning; consolidated here).

### Added
- **Modular AI pipeline system** — `app/ai/`: pipeline ABC + `PipelineResult` + provenance (`base.py`), NDVI/NDWI/EVI/BSI band math + z-scores (`preprocessing.py`), registry (`registry.py`), DB-backed model registry (`repository.py`), and 7 pipelines: `vegetation`, `land_change`, `infrastructure`, `environmental`, `anomaly`, `wildfire`, `flood`.
- **Satellite data** — provider interface + deterministic demo provider + real Copernicus Data Space Ecosystem (Sentinel Hub) provider with OAuth; `source="demo"` always maps to simulated provenance.
- **Capability registry** — `GET /system/capabilities` indexes all subsystems/pipelines; centralized `APP_VERSION`.
- **Robotics foundation** — `app/robotics/core` abstractions, navigation/perception/control/simulation, telemetry logging.
- **CubeSat system** — `app/spacecraft` subsystem simulation (3U).
- **Multi-planetary AI** — `app/multiplanetary` 7-layer decision stack, mission ops (comms/radiation/fail-safe/security), space-resource program (ISRU).

## [0.0.x] — 2026 H1 — Foundation

- Backend MVP: FastAPI, SQLAlchemy + GeoAlchemy2, postGIS, Alembic migrations, Pydantic v2 schemas.
- Sentinel Hub NDVI provider + demo provider + tests.
- RQ job queue + `worker.py` for queued analysis runs (survive API restarts).
- Auth hardening: bcrypt-style hashing, JWT + jti revocation, login lockout, per-IP rate limiting (auth endpoints stricter), SECRET_KEY production guard.
- Docker Compose (PostGIS + Redis + worker) and Dockerfile with Alembic entry.
- Frontend: React + Vite + TypeScript, landing page, `/app` dashboard routes wired to the API.