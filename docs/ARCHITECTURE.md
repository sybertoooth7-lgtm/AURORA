# 🏗️ AURORA Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     AURORA PLATFORM v0.2.0                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │   WEB UI     │  │   API        │  │  API CLIENTS   │    │
│  │ (React/Vite) │  │  CLIENTS     │  │  (Partners)    │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────┘    │
│         │                 │                    │             │
│         └─────────────────┼────────────────────┘             │
│                           │                                  │
│                    ┌──────▼──────────┐                       │
│                    │   FASTAPI       │                       │
│                    │   Backend       │                       │
│                    │   (Port 8000)   │                       │
│                    └──────┬──────────┘                       │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐                │
│         │                 │                 │                │
│    ┌────▼────┐  ┌────────▼────────┐  ┌─────▼────┐         │
│    │PostgreSQL│  │ Redis (RQ +    │  │  RQ      │         │
│    │ + PostGIS│  │ lockout/redis) │  │  Worker  │         │
│    └──────────┘  └────────────────┘  └──────────┘         │
│                                                               │
│  ┌─────────────── CAPABILITY REGISTRY ───────────────────┐  │
│  │ satellite │ ai │ robotics │ spacecraft │               │  │
│  │ multiplanetary │ space_resources                       │  │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│      GET /system/capabilities  →  every subsystem + pipeline │
└─────────────────────────────────────────────────────────────┘
```

## Integration model

AURORA evolves as modular, independently-testable subsystems.  The
**capability registry** (`backend/app/capabilities.py`, exposed at
`GET /system/capabilities`) is the single index of what the platform can do:

```json
{
  "platform": "AURORA",
  "version": "0.2.0",
  "subsystems": [
    {"id": "satellite",         "modules": ["app.satellite"],         "status": "active"},
    {"id": "ai",                "modules": ["app.ai"],                "status": "active"},
    {"id": "robotics",          "modules": ["app.robotics"],          "status": "active"},
    {"id": "spacecraft",        "modules": ["app.spacecraft"],        "status": "active"},
    {"id": "multiplanetary",    "modules": ["app.multiplanetary"],    "status": "active"},
    {"id": "space_resources",   "modules": ["app.space_resources"],   "status": "active"}
  ],
  "ai_pipelines": [...],       // live: mirrored from the AI registry
  "satellite_sources": [...]   // live: real vs simulated boundary
}
```

Adding a future capability (constellation command, ISRU plant control,
orbital robotics) means adding one subsystem entry — the core system,
database, and API contract do not change.

## Backend Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|----------|
| **Framework** | FastAPI + uvicorn | Async web framework (single source of version: `settings.APP_VERSION`) |
| **Database** | PostgreSQL + PostGIS | Relational data + geometry (SQLAlchemy 2.x / GeoAlchemy2) |
| **Cache** | Redis | RQ job queue, login lockout counters, token blocklist |
| **Task Queue** | RQ (worker.py) | Analysis execution survives API restarts (not Celery) |
| **Validation** | Pydantic v2 | Schemas in `app/schemas/` |
| **Container** | Docker + docker-compose | API + worker + Postgres + Redis |
| **Config** | pydantic-settings | Single `Settings` class, `.env`, fail-fast secret guard |

### Module layout (`backend/app/`)

| Path | Responsibility |
|---|---|
| `config.py` | Central settings (`APP_VERSION`, DB, security, satellite, queue, AI) |
| `database.py`, `queue.py` | SQLAlchemy session bound to `get_db`; RQ Redis bindings |
| `security.py` | JWT auth, RBAC (`require_admin`), login lockout |
| `exceptions.py`, `logging_conf.py` | Uniform error codes + structured logging |
| `capabilities.py` | Platform-wide capability registry |
| `models/` | SQLAlchemy ORM: User, Analysis(+Result), SatelliteImage, Alert, AIModel |
| `schemas/` | Pydantic request/response models |
| `routes/` | FastAPI routers: health, system, auth, analysis, satellite, alerts, reports, ai |
| `services/` | Business logic boundary (`analysis_runner`) |
| `satellite/` | Provider interface (`SatelliteObservation`), demo + Sentinel Hub providers |
| `ai/` | Pipeline framework: registry, 7 pipelines, preprocessing, model repository, inference |
| `robotics/` | Terrestrial robot: core, navigation, perception, control, simulation, telemetry |
| `spacecraft/` | AURORA-1 3U CubeSat: ADCS, power, thermal, comms, payload, FSW, mission |
| `multiplanetary/` | 7-layer AI stack + ops (comms delay, radiation, disconnected, fail-safe, security) |
| `space_resources/` | ISRU: TRL registry, extraction, plant sim, economics, prospecting, roadmap |

### API Endpoints

```
/system
  GET /capabilities            # platform capability index (public)

/health
  GET /                        # health + version (public)
  GET /ready                   # readiness probe (public)

/auth
  POST /register  POST /token  # JWT auth with lockout + rate limiting
  GET  /me                     # current profile

/analysis
  POST /                       # create analysis (queued to RQ worker)
  GET  /                       # list analyses
  GET  /{id}                   # details
  GET  /{id}/results           # results

/satellite
  GET /images                  # satellite image list
  GET /sources                 # available data sources
  GET /images/{id}             # specific image

/ai
  GET  /pipelines              # pipeline registry (public)
  POST /infer                  # synchronous inference (auth)
  GET  /models  POST /models   # model registry (auth)
  PATCH /models/{id}/status    # promote/archive (admin)

/alerts
  GET  /                       # list alerts (auth)

/reports
  GET  /{analysis_id}          # report export (auth)
```

### Data models (SQLAlchemy + PostGIS)

```
User ─┬─< Analysis ──< AnalysisResult
      └─< Alert ──< AnalysisResult
SatelliteImage
AIModel                     # ai_models registry (prototype/production/archived)
```

Schema is owned by **Alembic** (`alembic upgrade head`; Dockerfile runs it
automatically).  Migrations:
`db5c3b1b933e` (initial), `a1b2c3d4e5f6` (+AI models + 3 analysis types),
`b5c6d7e8f9a0` (+wildfire/flood types).

### AI pipeline flow

```
POST /analysis  or  POST /ai/infer
        ↓
Provider boundary (demo ⇄ Sentinel Hub when credentials configured)
        ↓
SatelliteObservation(+history)
        ↓
PipelineRegistry → selected pipeline (vegetation/land_change/.../flood)
        ↓
PipelineResult (severity, confidence, findings, metrics)
        ↓
Persist Analysis + AnalysisResult + (Alert if severity ≥ 0.35)
        ↓
Dashboard / alerts / report
```

## Security Architecture

- JWT access tokens (HS256), 30 min expiry, per-account login lockout
  (5 attempts → 15 min) stored in Redis.
- Auth rate limiting (10 req/min per IP) vs. general 120 req/min.
- `require_admin` gate on irreversible governance actions
  (model promotion/archive).
- Production secrets guard: placeholders rejected when
  `ENVIRONMENT != development`.
- Mission ops security: HMAC command auth, anti-replay, config integrity
  (`app/multiplanetary/ops/security.py`) for the space-autonomy domain.

## Deployment

- **Dev**: local venv + Postgres + Redis + `uvicorn` (reload) + `python worker.py`.
- **Prod (docker-compose.yml)**: `api`, `worker`, `postgres`, `redis` services.
- **Target (future)**: Kubernetes with FastAPI replicas, DB/Redis HA.

## Monitoring & Logging

- Structured logging (`LOG_FORMAT=text|json`) via `app/logging_conf.py`;
  every request + every pipeline run is logged with `extra_keys`.
- Metrics tracked: request duration/status, pipeline runs, model promotion,
  security events.  Future: Prometheus/Grafana/Sentry.

---

**This architecture is designed to scale from a startup to a multi-planetary company.**