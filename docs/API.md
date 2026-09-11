# 🔌 AURORA API Documentation

## Overview

AURORA Backend API provides endpoints for:
- Health checks
- Satellite data analysis
- Analysis management
- Alert handling
- Robotics control (future)
- Mission planning (future)

## Base URL

```
http://localhost:8000
http://api.aurora-space.com (production)
```

## Authentication

Endpoints requiring authentication use JWT tokens:

```
Authorization: Bearer <token>
```

Register with `POST /auth/register`, then exchange the username and password at
`POST /auth/token` to receive a bearer token. Analysis, alert, and report
endpoints are scoped to the authenticated user.

## Endpoints

### Health

#### Health Check

```http
GET /health/
```

**Response:**

```json
{
  "status": "healthy",
  "service": "AURORA Backend",
  "version": "0.1.0"
}
```

#### Readiness Check

```http
GET /health/ready
```

**Response:**

```json
{
  "ready": true,
  "message": "AURORA backend is ready to serve requests"
}
```

### Analysis

#### Create Analysis

```http
POST /analysis/
Content-Type: application/json

{
  "analysis_type": "vegetation_stress",
  "latitude": -1.2,
  "longitude": 36.8,
  "radius_km": 50,
  "description": "Farm near Nairobi"
}
```

**Response (201):**

```json
{
  "id": 1,
  "user_id": 1,
  "analysis_type": "vegetation_stress",
  "status": "pending",
  "description": "Farm near Nairobi",
  "created_at": "2026-09-09T12:00:00Z",
  "completed_at": null
}
```

#### Get Analysis

```http
GET /analysis/{analysis_id}
```

**Response (200):**

```json
{
  "id": 1,
  "user_id": 1,
  "analysis_type": "vegetation_stress",
  "status": "completed",
  "description": "Farm near Nairobi",
  "created_at": "2026-09-09T12:00:00Z",
  "completed_at": "2026-09-09T12:05:30Z"
}
```

#### List Analyses

```http
GET /analysis/?skip=0&limit=100
```

**Response (200):**

```json
[
  {
    "id": 1,
    "user_id": 1,
    "analysis_type": "vegetation_stress",
    "status": "completed",
    "description": "Farm near Nairobi",
    "created_at": "2026-09-09T12:00:00Z",
    "completed_at": "2026-09-09T12:05:30Z"
  }
]
```

#### Get Analysis Results

```http
GET /analysis/{analysis_id}/results
```

**Response (200):**

```json
{
  "results": [
    {
      "id": 1,
      "severity_score": 0.42,
      "confidence": 0.85,
      "finding": "Vegetation stress detected in the analysis area",
      "metadata_json": "{\"source\":\"sentinel-2\"}",
      "created_at": "2026-09-09T12:05:30Z"
    }
  ]
}
```

The analysis request stores the requested latitude, longitude, and radius as a
PostGIS polygon. Creating an analysis queues a background task. The default
local provider is deterministic demo data; production deployments should
replace it with a live Sentinel or Landsat adapter.

### Satellite

#### List Satellite Images

```http
GET /satellite/images?source=Sentinel-2&skip=0&limit=100
```

**Response (200):**

```json
[
  {
    "id": 1,
    "source": "Sentinel-2",
    "image_id": "S2A_MSIL2A_20260909T073611_N0301_R063_T37MBR_20260909T074609",
    "date_acquired": "2026-09-09T07:36:11Z",
    "cloud_coverage": 0.15,
    "resolution_m": 10,
    "url": "https://..."
  }
]
```

#### Get Available Sources

```http
GET /satellite/sources
```

**Response (200):**

```json
{
  "sources": [
    "Sentinel-2",
    "Sentinel-1",
    "Landsat-8",
    "Landsat-9"
  ]
}
```

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid request parameters"
}
```

### 404 Not Found

```json
{
  "detail": "Analysis not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error"
}
```

## Analysis Types

- `vegetation_stress` - Vegetation stress detection (agriculture)
- `land_change` - Land change detection (land intelligence)
- `climate_impact` - Climate impact analysis (environmental)
- `infrastructure_change` - Infrastructure change detection
- `water_monitoring` - Water body monitoring (environmental)
- `infrastructure_monitoring` - Infrastructure/site monitoring
- `environmental_monitoring` - Combined water + ecosystem stress monitoring
- `anomaly_detection` - Statistical anomaly detection vs. an area's own history
- `wildfire_risk` - Wildfire fuel/dryness risk (proxy-based prototype)
- `flood_monitoring` - Flood/inundation detection (NDWI vs baseline; prototype)

## Status Codes

- `pending` - Analysis queued, waiting to start
- `processing` - Analysis in progress
- `completed` - Analysis completed successfully
- `failed` - Analysis failed

## AI Pipelines

Every analysis type is served by a *pipeline* (see `backend/app/ai/`). Results
carry explicit provenance -- `"provenance": "real"` for real Sentinel-2 data,
`"simulated"` for the deterministic demo provider -- plus a `model` object
whose `kind` (prototype|production) discloses whether the approach is validated
for operational use or an in-progress prototype. Simulated results are never
presented as real.

### List Pipelines

```http
GET /ai/pipelines
```

Public. Describes every registered pipeline: name, description, handles
(analysis types), model identity, preprocessing, and data requirements.

### Synchronous Inference

```http
POST /ai/infer
Content-Type: application/json
Authorization: Bearer <token>

{
  "analysis_type": "anomaly_detection",
  "latitude": -1.2,
  "longitude": 36.8,
  "radius_km": 5,
  "use_history": true,
  "description": "Site anomaly check"
}
```

Runs the pipeline for `analysis_type` synchronously over the area, then persists
the run as a completed analysis (same record/alert/report flow as queued runs)
so it appears in the dashboard.

**Response (200):**

```json
{
  "result": {
    "analysis_type": "anomaly_detection",
    "severity": 0.61,
    "confidence": 0.88,
    "findings": ["Anomaly flagged in ndvi (robust z-score 4.02); 3 index dimensions checked."],
    "metrics": { "ndvi": 3.9, "change_score": 1.2, "peak_zscore": 4.02 },
    "provenance": "real",
    "simulated": false,
    "source": "sentinel-2-l2a",
    "image_id": "cdse-20260909T000000Z-...",
    "acquired_at": "2026-09-09T00:00:00Z",
    "model": { "name": "statistical:robust-zscore", "version": "1.0.0", "kind": "prototype" },
    "preprocessing": ["median/MAD normalization", "per-index robust z-scores"],
    "labels": [{ "class": "anomaly", "confidence": 0.88, "attributes": {} }],
    "warning": null,
    "history_length": 8
  },
  "created_analysis_id": 42
}
```

### Model Management

```http
GET /ai/models                      # list model versions (auth)
GET /ai/models/{model_id}           # model details (auth)
POST /ai/models                     # register a model version (auth)
PATCH /ai/models/{model_id}/status  # promote/archive (admin only)
```

New model versions are always registered as `prototype`; only an **admin** can
raise a model to `production` (a governance gate), so prototypes can never
self-declare as production.

## Rate Limiting (TODO)

API endpoints are rate-limited:
- Free tier: 100 requests/hour
- Premium tier: 1000 requests/hour

## Pagination

Use `skip` and `limit` query parameters:

```http
GET /analysis/?skip=0&limit=50
```

---

### Parametric Agriculture Insurance

```http
GET  /insurance/defaults                  # public trigger defaults + policy limit
POST /insurance/trigger-check             # run insurance-index pipeline + apply trigger (auth)
```

`POST /insurance/trigger-check` accepts area coordinates, a `sum_insured_usd`,
and an optional `trigger_threshold` (defaults to the platform value from
`/insurance/defaults`). The response discloses whether the prototype trigger
has been breached and returns an honest *estimate* (never a settlement).

The run is persisted under the authenticated user so the dashboard / alerts
see it.

---

### Robotics Field Services

```http
POST /robotics/flights/{flight_id}/telemetry   # ingest one MQTT-style frame (auth)
GET  /robotics/flights/{flight_id}              # flight summary + health (auth)
POST /robotics/inspect                          # post-flight NDVI inspection report (auth)
```

Telemetry frames are stored in an in-memory, bounded, per-process store.
`/robotics/inspect` fuses the satellite damage proxy with the robot's flight
health (when `flight_id` is supplied) and persists the run as an analysis
result.

---

### Onboarding

```http
GET  /onboarding/status           # dynamic progress checklist (auth)
POST /onboarding/complete         # mark onboarding finished (auth)
POST /onboarding/first-analysis   # guided first-analysis execution (auth)
```

The checklist adapts to the user's current progress (analysis count, live
data configured) and includes explicit instructions when Sentinel Hub OAuth
credentials have not yet been set up.

---

### Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

**API Version**: 0.2.0  
**Last Updated**: 2026-09-11
