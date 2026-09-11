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
& "C:\Users\NEC\AppData\Local\Temp\opencode\aurora-venv\Scripts\python.exe" -m ruff check .

# Type check
& "C:\Users\NEC\AppData\Local\Temp\opencode\aurora-venv\Scripts\python.exe" -m mypy app

# Tests (excludes Redis-dependent auth-hardening tests locally)
& "C:\Users\NEC\AppData\Local\Temp\opencode\aurora-venv\Scripts\python.exe" -m pytest tests/ --ignore=tests/test_auth_hardening.py -p no:warnings
```

Expect exactly **281 tests passing**, `ruff` and `mypy` clean.

For the frontend type-check/build:

```powershell
# from aurora-frontend/
npm.cmd run build
```

## Environment notes

- The working venv has **no `pip` module**. Install packages with `uv`:
  `& "C:\Users\NEC\.local\bin\uv.exe" pip install --python "C:\Users\NEC\AppData\Local\Temp\opencode\aurora-venv\Scripts\python.exe" <package>`
- No local Postgres/Redis/Docker. As a result:
  - **Alembic migrations cannot be run locally** — they are validated in CI (`alembic upgrade head` against PostGIS 16).
  - **`tests/test_auth_hardening.py` needs Redis** and stays excluded from local runs; CI runs the full suite.
- Real Sentinel-2 data requires `SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` (Copernicus Data Space); otherwise the deterministic demo provider is used.

## Honesty invariants (do not break)

- **Provenance**: `source="demo"` must map to `Provenance.SIMULATED`; real sources (`sentinel-2-l2a`, landsat, sentinel-1) map to `Provenance.REAL`. Simulated results must always be flagged honestly (insurance warnings, onboarding next-step, `simulated` field).
- **Estimates are never settlements**: insurance payouts and damage proxies are estimates until validated against ground truth.
- Do not rewrite working, tested code for style reasons alone. When fixing a lint/type finding, prefer the smallest behavior-preserving change.

## Conventions

- No code comments unless they explain a non-obvious invariant (and referenced in ruff ignore explanations if relevant).
- SQLAlchemy models are legacy untyped `Column(...)` declarations; the Column-typing noise is scoped in `backend/pyproject.toml` under `[tool.mypy] disable_error_code` — do not fight that; add genuine fixes instead.
- Enums stay `(str, Enum)` — serialization must not change (UP042 ignored deliberately). Empty ABC stubs are intentional interface markers (B027 ignored deliberately).
- Schema changes go through Alembic migrations (never `create_all` autocrud).
- New pipeline code follows the contract in `app/ai/base.py` (`Pipeline`, `PipelineResult`, `SatelliteObservation` as the only observation input) and is registered in `app/ai/registry.py::build_workspace_pipelines`.
- Adding an endpoint means: router in `app/routes/`, Pydantic schemas in `app/schemas/`, registration in `app/routes/__init__.py` + `app/main.py`, canonical Swagger tag in `openapi_tags`, and a test.