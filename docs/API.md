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

#### Current User

```http
GET /auth/me
Authorization: Bearer <access-token>
```

Returns the authenticated user's profile from the database. Clients should use
this endpoint instead of decoding JWT claims to build a profile.

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

- `vegetation_stress` - Vegetation stress detection
- `land_change` - Land change detection
- `climate_impact` - Climate impact analysis
- `infrastructure_change` - Infrastructure change detection
- `water_monitoring` - Water body monitoring

## Status Codes

- `pending` - Analysis queued, waiting to start
- `processing` - Analysis in progress
- `completed` - Analysis completed successfully
- `failed` - Analysis failed

## Rate Limiting

API requests are limited per client IP using an atomic Redis counter shared by
all API instances. The current default is 120 requests per 60-second window.
The response includes `X-RateLimit-Limit` and `X-RateLimit-Remaining`; requests
over the limit receive `429` with a `Retry-After` header.

## Pagination

Use `skip` and `limit` query parameters:

```http
GET /analysis/?skip=0&limit=50
```

## Interactive Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

**API Version**: 0.1.0  
**Last Updated**: 2026-09-09
