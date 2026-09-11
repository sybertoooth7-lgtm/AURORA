```markdown
# AURORA Backend

Space Intelligence Platform - Multi-planetary space technology infrastructure

## 🚀 Overview

AURORA is a comprehensive backend system for:
- **Satellite Intelligence**: AI-powered analysis of satellite imagery
- **Geospatial Analytics**: Land monitoring, vegetation stress, climate intelligence
- **Autonomous Systems**: Integration with robotics and orbital platforms
- **Space Operations**: Mission planning and infrastructure management

## 📋 Tech Stack

- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL + PostGIS (geospatial)
- **Cache**: Redis
- **Satellite data**: Copernicus Data Space Ecosystem (Sentinel Hub Statistical API) for real Sentinel-2 NDVI, with a deterministic demo provider as fallback
- **Containerization**: Docker & Docker Compose
- **API Format**: RESTful JSON

## 🗂️ Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py              # Configuration management
│   ├── database.py            # Database setup
│   ├── logging_conf.py        # Structured logging (text or JSON)
│   ├── exceptions.py          # Error hierarchy mapped to HTTP responses
│   ├── models/                # SQLAlchemy models
│   │   ├── user.py
│   │   ├── analysis.py
│   │   ├── satellite_imagery.py
│   │   ├── alert.py
│   │   └── ai_model.py        # Model/metadata registry
│   ├── schemas/               # Pydantic validation schemas
│   │   ├── user.py
│   │   ├── analysis.py
│   │   ├── satellite.py
│   │   └── ai.py
│   ├── routes/                # API endpoints
│   │   ├── health.py
│   │   ├── analysis.py
│   │   ├── satellite.py
│   │   ├── auth.py
│   │   ├── alerts.py
│   │   ├── reports.py
│   │   └── ai.py              # AI pipelines, infer, model management
│   ├── ai/                    # Modular AI pipeline system
│   │   ├── __init__.py
│   │   ├── base.py            # Pipeline ABC, PipelineResult, provenance
│   │   ├── preprocessing.py   # NDVI/NDWI/EVI/BSI math, z-scores
│   │   ├── registry.py        # analysis-type -> pipeline resolution
│   │   ├── repository.py      # DB-backed model registry
│   │   ├── vegetation.py      # agriculture: vegetation stress
│   │   ├── land_change.py     # land intelligence: change detection
│   │   ├── infrastructure.py  # infrastructure / site monitoring
│   │   ├── environmental.py   # water + ecosystem / climate monitoring
│   │   ├── anomaly.py         # robust-zscore anomaly detection
│   │   └── computer_vision.py # PROTOTYPE torch-based vision (optional deps)
│   └── satellite/             # Satellite data providers
│       ├── providers.py       # Provider interface + demo provider + factory
│       └── sentinel_hub.py    # Real Copernicus Data Space Ecosystem (Sentinel Hub) provider
├── alembic/                    # Database migrations (schema is owned here, not by create_all)
│   ├── env.py
│   └── versions/
├── main.py                    # FastAPI application
├── worker.py                   # RQ worker entrypoint -- runs analysis jobs
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Container configuration
├── docker-compose.yml         # Local development environment
├── .env.example              # Environment variables template
└── README.md                 # This file
```

## 🔧 Setup

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone https://github.com/sybertoooth7-lgtm/AURORA.git
cd AURORA/backend

# Create .env file
cp .env.example .env

# Start services (postgres, redis, api, worker).
# The api and worker containers each run `alembic upgrade head` on
# startup before serving traffic / picking up jobs.
docker-compose up -d

# Check health
curl http://localhost:8000/health/
```

### Option 2: Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Setup database (requires PostgreSQL with PostGIS) and Redis
# Update DATABASE_URL / REDIS_URL in .env if not using the defaults

# Apply database migrations
alembic upgrade head

# Run the API
uvicorn main:app --reload

# In a separate terminal, run the worker (required -- analysis jobs are
# processed here, not inline in the API request)
python worker.py
```

### Database migrations

Schema changes go through Alembic, not `Base.metadata.create_all()`. After
changing a model in `app/models/`:

```bash
alembic revision --autogenerate -m "describe the change"
# review the generated file in alembic/versions/ -- autogenerate gets most
# of it right but always check it, especially anything touching a
# geoalchemy2 Geometry column or a Postgres Enum
alembic upgrade head
```

## 📚 API Endpoints

### Health
- `GET /health/` - Health check
- `GET /health/ready` - Readiness check

### Analysis
- `POST /analysis/` - Create new analysis
- `GET /analysis/{analysis_id}` - Get analysis details
- `GET /analysis/{analysis_id}/results` - Get analysis findings
- `GET /analysis/` - List analyses

### Authentication and operations
- `POST /auth/register` - Create an account
- `POST /auth/token` - Exchange credentials for a JWT
- `GET /alerts` - List the current user's alerts
- `POST /alerts/{alert_id}/acknowledge` - Acknowledge an alert
- `GET /reports/{analysis_id}?format=json|csv` - Export an analysis report

### Satellite
- `GET /satellite/images` - List satellite images
- `GET /satellite/sources` - Get available data sources

### AI pipeline system
- `GET /ai/pipelines` - List registered AI pipelines (public)
- `POST /ai/infer` - Run a pipeline synchronously over an area (auth)
- `GET /ai/models` - List model versions (auth)
- `POST /ai/models` - Register a model version (auth; starts as prototype)
- `PATCH /ai/models/{id}/status` - Promote to production / archive (admin)

Every AI result carries explicit **provenance** (`real` vs `simulated`) and a
**model** identity whose `kind` is `prototype` or `production`. Results from the
deterministic demo provider are always disclosed as `simulated`; nothing is ever
reported as real data unless it came from a real sensor. Only admins can promote
a model to `production`, so prototypes can never self-declare as validated.

## 🗄️ Database Models

### Users
User accounts with authentication

### SatelliteImage
Metadata for satellite imagery from Sentinel, Landsat, etc.

### Analysis
Analysis jobs for vegetation stress, land changes, climate impact

### AnalysisResult
Results and findings from analysis

### Alert
Significant findings requiring user attention

## 🛰️ Satellite Data Pipeline

### Current
- Real Sentinel-2 L2A NDVI (+ NDWI, EVI when available) via the Copernicus Data Space Ecosystem's free Statistical API (server-side cloud masking + area-mean indices, no raster processing needed locally)
- Change score computed by comparing the latest reading to the trailing baseline for the same area
- Time-series `fetch_history()` supports history-aware pipelines (anomaly detection, land change)
- Falls back to a deterministic demo provider when `SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` aren't set, so local dev and tests don't need real credentials

### AI Pipelines (modular, app/ai)

| Pipeline | Analysis types | Approach | Model kind |
|---|---|---|---|
| `vegetation` | vegetation_stress | NDVI level + change blend | band-math (prototype) |
| `land_change` | land_change | Change score + robust z-score vs. history | statistical (prototype) |
| `infrastructure` | infrastructure_change, infrastructure_monitoring | BSI surface proxy + change | rules (prototype) |
| `environmental` | climate_impact, water_monitoring, environmental_monitoring | NDWI water + NDVI/EVI ecosystem | rules (prototype) |
| `anomaly` | anomaly_detection | Median/MAD robust z-scores over history | statistical (prototype) |
| `wildfire` | wildfire_risk | Dry-vegetation + bare-surface + moisture-deficit composite | composite-index (prototype) |
| `flood` | flood_monitoring | NDWI current vs. area baseline (z-score excess) | statistical (prototype) |

Designed so future modules (pixel-level segmentation, autonomous robotics
perception, spacecraft/planetary surface mapping) slot into the same
`Pipeline -> PipelineResult` contract without changing the registry, API, or
result schema. Model-management endpoints track versions and gate
prototype -> production promotion behind admin action.

### Future Capabilities
- Land change detection from imagery (not just NDVI stats)
- Autonomous robotic control
- Mission planning algorithms
- Predictive analytics
- Distributed AI for orbital systems

## 🔐 Security

Implemented:
- Password hashing: PBKDF2-HMAC-SHA256, 120,000 rounds, per-user salt, constant-time comparison
- Password/username length limits enforced server-side (not just in the frontend)
- Login is timing-safe against username enumeration -- a nonexistent username does the same PBKDF2 work as a wrong password against a real one
- Per-account login lockout (5 failed attempts -> 15 min lock, Redis-backed, keyed by username so it can't be bypassed by spraying attempts from many IPs)
- JWT access tokens carry a `jti`; `/auth/logout` revokes the current token immediately via a Redis blocklist rather than waiting for natural expiry
- Two-tier rate limiting: a stricter per-IP budget on `/auth/token` and `/auth/register` than on general API traffic
- The app refuses to start with `ENVIRONMENT` set to anything other than `development` unless `SECRET_KEY` has been changed from the placeholder and is at least 32 characters
- Role-gated actions: promoting an AI model to `production` requires `is_admin` (`require_admin` in app/security.py)
- Structured request/error logging with severity-aware JSON output; expected application errors return stable `code` + `detail` bodies

Still remaining:
- API key management (for machine-to-machine / integration use, not just user login)
- Rate limiting is still per-process/in-memory -- fine for one instance, needs to move to Redis before running multiple API replicas
- No password reset / email verification flow

## 📊 Development

The dependency manifest is `requirements.txt`. The API stores a geospatial area
of interest and enqueues execution onto an RQ queue backed by Redis
(`app.queue`); `worker.py` is a separate process that pulls jobs off that
queue and runs `app.services.analysis_runner.run_analysis`, which fetches an
observation (and history) through `app.satellite.providers.get_satellite_provider()`
and runs the pipeline registered for the analysis type via `app.ai` -- the
real `SentinelHubProvider` (Copernicus Data Space Ecosystem) when
`SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` are set, or the deterministic
`DemoSatelliteProvider` otherwise (results then report `simulated`). Running
the worker is required for analyses to ever leave "pending" -- the API process
no longer runs them in-process. The current rate limiter is process-local; use
Redis for multi-instance deployment of that too.

### Running Tests
```bash
# From backend/. pyproject.toml sets pythonpath so `app` and `main` resolve.
pytest
# All AI-pipeline / provider / security tests run offline.
# tests/test_auth_hardening.py additionally needs a local Redis
# (redis-server, or `docker-compose up -d redis`).
```

### Code Style
```bash
black .
flake8 .
isort .
mypy .
```

## 🌍 Deployment

### Production Checklist
- [ ] Update SECRET_KEY in .env
- [ ] Set ENVIRONMENT=production
- [ ] Restrict CORS origins
- [ ] Configure database backups
- [ ] Setup monitoring/logging
- [ ] Configure error tracking
- [ ] Setup CI/CD pipeline

## 📖 API Documentation

Interactive API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🚀 Roadmap

**Phase 1 (2026)**: Space Intelligence MVP
- Satellite data integration
- Vegetation stress detection
- Web dashboard

**Phase 2 (2027)**: Autonomous Robotics
- Field robot integration
- Autonomous navigation
- Real-time monitoring

**Phase 3 (2028+)**: Space Hardware
- CubeSat technology
- Orbital operations
- Multi-planetary AI

## 📝 License

MIT

## 👥 Contributing

See CONTRIBUTING.md for guidelines

## 📧 Contact

info@aurora-space.com

---

**Building the technologies and economic infrastructure that allow humanity to explore, inhabit and responsibly utilize the Solar System.** 🌌
```
