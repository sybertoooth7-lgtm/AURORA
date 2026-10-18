# AGENTS.md

Guidance for AI coding agents working in this repository.

## Repository layout

- `backend/` — FastAPI application (Python 3.11). All backend work happens here.
- `aurora-frontend/` — React + Vite + TypeScript web app.
- `.github/workflows/ci.yml` — CI gates (they must keep passing).

## Verified gates (run before considering work complete)

All commands run from `backend/`:

```powershell
# Lint
& ".\.venv\Scripts\python.exe" -m ruff check .

# Type check
& ".\.venv\Scripts\python.exe" -m mypy app main.py

# Tests (full suite -- demo mode provides the SQLite DB + in-memory Redis
# substitute locally, so the Redis-dependent tests now run here too)
& ".\.venv\Scripts\python.exe" -m pytest tests/ -p no:warnings
```

Expect exactly **575 tests passing**, `ruff` and `mypy` clean. The venv
lives in `backend/.venv`; if it has been recreated elsewhere, substitute
that path. Note that this shell can truncate pytest's summary line --
confirm a run by its exit code, not by reading the last line of stdout.

For the frontend:

```powershell
# from aurora-frontend/
npm.cmd run build   # tsc -b && vite build
npm.cmd run lint    # oxlint
```

## Environment notes

- The toolchain is pinned in `backend/requirements-dev.txt` (`ruff==0.16.7`, `mypy==2.3.1`) so local results and CI results are identical. Prefer `uv` to install anything into the venv:
  `& "C:\Users\NEC\.local\bin\uv.exe" pip install --python ".\.venv\Scripts\python.exe" <package>`
  (a pip was bootstrapped via `ensurepip` if uv is ever unavailable, but uv is the reliable path).
- No local Postgres/Redis/Docker. As a result:
  - **Alembic migrations cannot be run locally** — they are validated in CI (`alembic upgrade head` against PostGIS 16).
  - **Demo mode** (`ENABLE_DEMO_MODE=true` in `backend/.env`) is the normal local dev path: the app + the full test suite run on an in-memory SQLite database and an in-memory Redis substitute (`app.queue._DemoRedis`, which implements the exact string/zset/getdel surface AURORA uses) with zero external services. `tests/conftest.py` creates the demo schema for in-process `TestClient` tests. `tests/test_demo_mode.py` exercises demo mode end-to-end via a subprocess (the flag cannot be flipped in-process: settings are `lru_cache`d and the engine is built at module import). Never import `geoalchemy2` when demo mode is on — its global SQLite dialect patches break the in-memory DB; `app.database.geometry_type()`/`area_geometry()` abstract that away.
- Real Sentinel-2 data requires `SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` (Copernicus Data Space) **and** `ENABLE_DEMO_MODE=false` — demo mode always uses the deterministic demo provider; otherwise the demo provider is used when credentials are absent.
- `gh` CLI is at `%LOCALAPPDATA%\Programs\gh\bin`. It authenticates CI checks via the token in the Windows Credential Manager (`git credential fill`), which lacks `read:org` — so use the GitHub REST API or git's stored creds, not `gh auth`.

## Honesty invariants (do not break)

- **Provenance**: `source="demo"` must map to `Provenance.SIMULATED`; real sources (`sentinel-2-l2a`, landsat, sentinel-1) map to `Provenance.REAL`. Simulated results must always be flagged honestly (insurance warnings, onboarding next-step, `simulated` field).
- **Estimates are never settlements**: insurance payouts and damage proxies are estimates until validated against ground truth.
- Do not rewrite working, tested code for style reasons alone. When fixing a lint/type finding, prefer the smallest behavior-preserving change.

## Conventions

- No code comments unless they explain a non-obvious invariant (and referenced in ruff ignore explanations if relevant).
- A test that asserts an analysis reached `completed` must pin `app.queue.get_analysis_queue` to `_InlineQueue` (see the autouse fixture in `tests/test_monitoring.py`). Demo mode does this itself; CI runs against a real Redis whose RQ queue has no worker, so an unpinned job sits queued forever and the assertions fail for environment reasons only.
- SQLAlchemy models are legacy untyped `Column(...)` declarations; the Column-typing noise is scoped in `backend/pyproject.toml` under `[tool.mypy] disable_error_code` — do not fight that; add genuine fixes instead.
- Enums stay `(str, Enum)` — serialization must not change (UP042 ignored deliberately). Empty ABC stubs are intentional interface markers (B027 ignored deliberately).
- Schema changes go through Alembic migrations (never `create_all` autocrud).
- New pipeline code follows the contract in `app/ai/base.py` (`Pipeline`, `PipelineResult`, `SatelliteObservation` as the only observation input) and is registered in `app/ai/registry.py::build_workspace_pipelines`.
- Adding an endpoint means: router in `app/routes/`, Pydantic schemas in `app/schemas/`, registration in `app/routes/__init__.py` + `app/main.py`, canonical Swagger tag in `openapi_tags`, and a test.
- Field-boundary analysis endpoints (`/crop/analyze`) accept a GeoJSON polygon, never a bare lat/lon plus `radius_km`; the survey area is derived in the route (`_survey_area` in `app/routes/crop.py`) and the boundary is stored via `area_geometry(boundary_wkt)` so dashboards/alerts see the same row the queued runner would produce. Provenance must appear in both the response body and the persisted `AnalysisResult.metadata_json`.
- Email verification is **enforced**: capability-gated write endpoints (create analysis, monitor, re-run, `/ai/infer`, insurance trigger-check, robotics inspect/simulate, onboarding first-analysis) use `require_verified` (403 `email_unverified`); reads and auth flows stay on `get_current_user`. API keys are `aur_`-prefixed JWTs-for-machines routed in `app.security.get_current_user` by prefix before the DB (sha256 hash at rest, plaintext shown once); keys live at `/auth/api-keys`.
- Operator bootstrap is the CLI (`backend/cli.py`), not a route: `create-admin`, `set-admin`, `revoke-admin`, `list-users`, `set-verified`. Password via `AURORA_CLI_PASSWORD` or an interactive prompt.