# Changelog

All notable changes to the AURORA platform. Dates are when the change landed on `main`.

## Unreleased

### Planned
- Redis-backed global rate limiting (current limiter is per-process in-memory).
- Real Sentinel-2 provider activation (requires `SENTINEL_CLIENT_ID` / `SENTINEL_CLIENT_SECRET`).

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