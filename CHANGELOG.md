# Changelog

All notable changes to the AURORA platform. Dates are when the change landed on `main`.

## Unreleased

### Added
- **Continuous monitoring** — `PATCH /analysis/{id}/monitor` sets a re-check cadence (bounded by `MONITOR_MIN_INTERVAL_MINUTES`), `POST /analysis/{id}/re-run` triggers an immediate re-check, both shown in the web dashboard (last/next check). A daemon-thread scheduler (`app/monitoring.py`) fires due re-checks onto the normal RQ worker and de-duplicates across API replicas with a per-analysis Redis lock; manual re-runs share the daily quota.
- **Demo mode** (`ENABLE_DEMO_MODE=true`) — the platform boots with zero external infrastructure: in-memory SQLite database + in-memory queue replace Postgres/PostGIS/Redis, analysis jobs execute inline, and all pipeline logic + the demo satellite provider run for real with `provenance=simulated`. End-to-end subprocess test in `tests/test_demo_mode.py`. With demo mode on locally, the entire test suite (including the Redis-dependent auth-hardening and rate-limiter tests) runs with no external services.
- **Admin API** — `GET/POST /admin/users...` for listing and disabling/enabling accounts (`app/routes/admin.py`); no self-serve admin-grant endpoint by design.
- **Email verification & password reset** — Redis-backed single-use tokens, provider-agnostic SMTP sender (`app/email.py`), verification/reset routes, JWT `token_version` invalidation on password change.
- **Redis-backed rate limiting** (`app/rate_limiter.py`) — sliding-window log via sorted sets, so the per-IP throttle holds across API replicas (replaces the per-process limiter); daily per-user analysis quota (`app/quota.py`).
- **Real Sentinel-2 provider activation** — the live Sentinel-2 L2A path (Copernicus Data Space Ecosystem) is now verified end-to-end with live credentials. Set `SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` in `backend/.env` (gitignored) and disable demo mode (`ENABLE_DEMO_MODE=false`) to receive real satellite observations (`source: sentinel-2-l2a`, `simulated: false`).

### Fixed
- Merged admin/verification/reset work was missing `app/schemas/admin.py` (referenced by `app/routes/admin.py`), which broke app import — schema added.
- Setting only one of `SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` used to silently fall back to the demo satellite provider; startup now logs a warning so partial config is loud.
- Docs corrected after the merged rate limiter: `docs/API.md` and `backend/README.md` no longer claim the limiter is per-process/in-memory, and the offline-suite note no longer requires a local Redis.
- The live Sentinel-2 Statistical API rejected requests with `400` ("pixel size exceeds the limit") because `resx`/`resy` were sent as meter values over a WGS84 degree bbox; resolution is now expressed in the bbox's CRS units (~10 m ≈ 8.98e-5 degrees).
- Demo mode now always uses the deterministic demo satellite provider, even when Sentinel credentials are configured, keeping demo fully deterministic and honest; live data is the explicit non-demo path.
- Onboarding's "Connect live satellite data" flag (`has_live_satellite`) now reflects the provider actually serving observations instead of only checking credentials, so demo mode can no longer claim a live source while serving simulated data.

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