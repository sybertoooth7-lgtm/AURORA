# 🏗️ AURORA Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   AURORA PLATFORM                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐    │
│  │              │  │              │  │                │    │
│  │   WEB UI     │  │ MOBILE APP   │  │  API CLIENTS   │    │
│  │ (React/Next) │  │   (Flutter)  │  │  (Partners)    │    │
│  │              │  │              │  │                │    │
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
│    │PostgreSQL│ │  Redis Cache    │  │  Celery  │         │
│    │ +PostGIS │ │                 │  │  Tasks   │         │
│    │          │ │  Geospatial     │  │          │         │
│    └──────────┘ │  Data Layer     │  └──────────┘         │
│                 └─────────────────┘                         │
│                                                               │
│  ┌──────────────────────────────────────────────┐           │
│  │         AI/ML SERVICES                       │           │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │           │
│  │  │ Computer │  │ Robotics │  │ Mission  │  │           │
│  │  │ Vision   │  │ Control  │  │ Planning │  │           │
│  │  └──────────┘  └──────────┘  └──────────┘  │           │
│  └──────────────────────────────────────────────┘           │
│                                                               │
│  ┌──────────────────────────────────────────────┐           │
│  │    EXTERNAL DATA SOURCES                     │           │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │           │
│  │  │ Sentinel │  │ Landsat  │  │Robotics  │  │           │
│  │  │ 2 & 1    │  │ 8 & 9    │  │Telemetry │  │           │
│  │  └──────────┘  └──────────┘  └──────────┘  │           │
│  └──────────────────────────────────────────────┘           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Backend Architecture

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|----------|
| **Framework** | FastAPI | Modern async Python web framework |
| **Database** | PostgreSQL | Main relational database |
| **Geospatial** | PostGIS | Geographic data extension |
| **Cache** | Redis | In-memory caching & session storage |
| **Task Queue** | Celery | Async task processing |
| **Message Broker** | Redis/RabbitMQ | Celery backend |
| **ORM** | SQLAlchemy | Object-relational mapping |
| **Validation** | Pydantic | Data validation & serialization |
| **Container** | Docker | Containerization |
| **Orchestration** | Kubernetes | Future: Production orchestration |

### Data Models

```
┌─────────────┐
│   Users     │
├─────────────┤
│ id (PK)     │
│ email       │
│ username    │
│ hashed_pwd  │
│ is_active   │
└──────┬──────┘
       │ (1:N)
       └──────────────┐
                      │
        ┌─────────────▼────────────┐
        │   Analyses               │
        ├─────────────────────────┤
        │ id (PK)                 │
        │ user_id (FK)            │
        │ analysis_type           │
        │ geometry (PostGIS)      │
        │ status                  │
        │ created_at              │
        └─────────────┬───────────┘
                      │ (1:N)
                      │
        ┌─────────────▼──────────────┐
        │  AnalysisResults          │
        ├──────────────────────────┤
        │ id (PK)                  │
        │ analysis_id (FK)         │
        │ result_geometry          │
        │ severity_score           │
        │ confidence               │
        │ finding                  │
        └──────────────────────────┘

┌────────────────────┐
│ SatelliteImages    │
├────────────────────┤
│ id (PK)            │
│ source             │
│ image_id           │
│ date_acquired      │
│ geometry (PostGIS) │
│ cloud_coverage     │
│ resolution_m       │
│ url                │
└────────────────────┘

┌────────────────┐
│   Alerts       │
├────────────────┤
│ id (PK)        │
│ user_id (FK)   │
│ result_id (FK) │
│ alert_type     │
│ title          │
│ description    │
│ is_read        │
└────────────────┘
```

### API Endpoints

```
/health
  GET /                    # Health check
  GET /ready               # Readiness probe

/analysis
  POST /                   # Create analysis
  GET /{id}                # Get analysis details
  GET /                    # List analyses
  GET /{id}/results        # Get analysis results

/satellite
  GET /images              # List satellite images
  GET /sources             # Available data sources
  GET /images/{id}         # Get specific image

/users (Future)
  POST /register           # User registration
  POST /login              # User login
  GET /me                  # Current user profile

/robotics (Future)
  GET /robots              # List robots
  GET /robots/{id}         # Robot status
  POST /robots/{id}/tasks  # Send task to robot

/missions (Future)
  GET /missions            # List missions
  POST /missions           # Create mission
  GET /missions/{id}       # Mission details
```

### Authentication (TODO)

```
User Login
   ↓
JWT Token Generation
   ↓
Refresh Token Storage (Redis)
   ↓
Request with Authorization Header
   ↓
Token Verification
   ↓
Role-Based Access Control (RBAC)
```

### Processing Pipeline

#### Analysis Processing

```
User Creates Analysis
         ↓
Request Validation (Pydantic)
         ↓
Analysis Record Created (DB)
         ↓
Celery Task Queued
         ↓
Satellite Data Retrieval
         ↓
Preprocessing (Georeferencing, etc.)
         ↓
AI/ML Analysis
         ↓
Results Storage (DB)
         ↓
Alert Generation (if needed)
         ↓
Notification to User
```

#### AI Pipeline

```
Satellite Image Input
         ↓
Normalization (0-1 range)
         ↓
Feature Extraction (ResNet50)
         ↓
Analysis Selection
         ├─→ Vegetation Stress (NDVI)
         ├─→ Land Change Detection
         ├─→ Climate Impact Analysis
         └─→ Infrastructure Monitoring
         ↓
Result Computation
         ↓
Geometric Polygon Generation
         ↓
Severity Scoring (0-1)
         ↓
Confidence Calculation
         ↓
Output Report
```

## Database Schema

### PostGIS Integration

All location-based data uses PostGIS geometry types:

```sql
-- Analysis geometry (polygon of analysis area)
CREATE TABLE analyses (
    id SERIAL PRIMARY KEY,
    geometry GEOMETRY(POLYGON, 4326),  -- WGS84 CRS
    ...
);

-- Create spatial index
CREATE INDEX idx_analyses_geom ON analyses USING GIST (geometry);

-- Query examples
SELECT * FROM satellite_images 
WHERE ST_Intersects(geometry, 
    ST_MakeEnvelope(-0.3, -1.3, 0.3, -1.0, 4326));
```

## Deployment Architecture

### Development

```
Local Machine
    ├── Python venv
    ├── PostgreSQL (local)
    ├── Redis (local)
    └── FastAPI (uvicorn reload)
```

### Production (Target)

```
Kubernetes Cluster
    ├── FastAPI Pods (replicas)
    ├── PostgreSQL StatefulSet
    ├── Redis Cache
    ├── Celery Workers
    ├── Ingress (Load Balancer)
    └── PersistentVolumes
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim
RUN apt-get install postgresql-client
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

## Scalability Considerations

### Horizontal Scaling
- Multiple FastAPI instances behind load balancer
- Database read replicas for queries
- Distributed Redis clusters
- Celery worker pool scaling

### Vertical Scaling
- Increase CPU/RAM for API servers
- Database performance tuning
- Connection pooling optimization

### Caching Strategy
- User session caching (Redis)
- Satellite image metadata caching
- Analysis result caching
- Computed geometry caching

## Security Architecture

```
┌─────────────────────┐
│  Internet           │
└──────────┬──────────┘
           │
        ┌──▼──────────────┐
        │ WAF/DDoS        │
        │ Protection      │
        └──┬──────────────┘
           │
        ┌──▼──────────────┐
        │ HTTPS/TLS       │
        │ Encryption      │
        └──┬──────────────┘
           │
        ┌──▼──────────────┐
        │ API Gateway     │
        │ Rate Limiting   │
        └──┬──────────────┘
           │
        ┌──▼──────────────┐
        │ Authentication  │
        │ (JWT Tokens)    │
        └──┬──────────────┘
           │
        ┌──▼──────────────┐
        │ RBAC            │
        │ Authorization   │
        └──┬──────────────┘
           │
        ┌──▼──────────────┐
        │ Application     │
        │ Logic           │
        └──┬──────────────┘
           │
        ┌──▼──────────────┐
        │ Database        │
        │ (Encrypted)     │
        └─────────────────┘
```

## Monitoring & Logging

### Metrics
- API response times
- Database query performance
- Celery task execution times
- Error rates
- User engagement

### Logging
- Application logs (INFO, WARNING, ERROR, DEBUG)
- Database query logs
- Celery task logs
- Access logs
- Security events

### Tools (Future)
- Prometheus: Metrics collection
- Grafana: Visualization
- ELK Stack: Log aggregation
- Sentry: Error tracking
- DataDog: APM

---

**This architecture is designed to scale from a startup to a multi-planetary company.**
