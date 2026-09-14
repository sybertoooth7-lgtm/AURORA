# Changelog

All notable changes to the AURORA platform. Dates are when the change landed on `main`.

## Unreleased

### Added
- **API keys** (`/auth/api-keys`) — mint/list/revoke machine credentials with the same bearer header as JWTs (`app/api_keys.py`, `app/models/api_key.py`, migration `3b7e9f1c2d5a`). Secrets are `aur_`-prefixed, SHA-256-hashed at rest, shown once at creation, revocable and optionally expiring; `get_current_user` routes by prefix before it ever hits the DB.
- **Email verification is now enforced** — capability-gated endpoints (new analyses, AI inference, insurance checks, robotics inspect/simulate, onboarding first-analysis) return `403 email_unverified` until the address is confirmed (`VerificationRequiredError`, `require_verified`); reads and the verification flow stay open. `GET /auth/me` exposes the profile (incl. `email_verified`) and the onboarding checklist gained an `email_verified` step.
- **Operator CLI** (`backend/cli.py`) — first-admin bootstrap and account administration without a second API route: `create-admin`, `set-admin`, `revoke-admin`, `list-users`, `set-verified`; password via `AURORA_CLI_PASSWORD` or an interactive prompt; bootstrap emails gated by `CLI_ADMIN_EMAIL_DOMAIN`.
- **Fleet dashboard API** — `GET /robotics/flights` (all flights, newest first), `GET /robotics/flights/{id}/telemetry` (paginated frames), `POST /robotics/simulate` (deterministic orbit survey openly labelled `is_simulated`) for the operations-fleet UI.
- **Web UI** — operations fleet page with flight health/KPIs, flight detail page with inline-SVG telemetry charts (battery, altitude, motor temp, GPS accuracy), post-flight satellite inspection panel, and a Settings page with account verification status + full API-key management (create with one-time secret reveal, list, revoke).

### Fixed
- Docs no longer claim API keys are unimplemented or that email verification is informational-only (both now shipped).

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