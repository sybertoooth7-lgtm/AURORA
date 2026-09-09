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
│   ├── models/                # SQLAlchemy models
│   │   ├── user.py
│   │   ├── analysis.py
│   │   ├── satellite_imagery.py
│   │   └── alert.py
│   ├── schemas/               # Pydantic validation schemas
│   │   ├── user.py
│   │   ├── analysis.py
│   │   └── satellite.py
│   ├── routes/                # API endpoints
│   │   ├── health.py
│   │   ├── analysis.py
│   │   └── satellite.py
│   └── satellite/             # Satellite data providers
│       ├── providers.py       # Provider interface + demo provider + factory
│       └── sentinel_hub.py    # Real Copernicus Data Space Ecosystem (Sentinel Hub) provider
├── main.py                    # FastAPI application
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

# Start services
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

# Setup database (requires PostgreSQL with PostGIS)
# Update DATABASE_URL in .env

# Run server
uvicorn main:app --reload
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
- Real Sentinel-2 L2A NDVI via the Copernicus Data Space Ecosystem's free Statistical API (server-side cloud masking + area-mean NDVI, no raster processing needed locally)
- Change score computed by comparing the latest reading to the trailing baseline for the same area
- Falls back to a deterministic demo provider when `SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` aren't set, so local dev and tests don't need real credentials

### Future Capabilities
- Land change detection from imagery (not just NDVI stats)
- Autonomous robotic control
- Mission planning algorithms
- Predictive analytics
- Distributed AI for orbital systems

## 🔐 Security (Remaining)

- JWT authentication and current-user scoping
- API key management
- Role-based access control
- Data encryption
- Rate limiting

## 📊 Development

The dependency manifest is `requirements.txt`. The API stores a geospatial area
of interest, queues execution with FastAPI background tasks, and fetches an
observation through `app.satellite.providers.get_satellite_provider()`, which
returns the real `SentinelHubProvider` (Copernicus Data Space Ecosystem) when
`SENTINEL_CLIENT_ID`/`SENTINEL_CLIENT_SECRET` are set in the environment, or the
deterministic `DemoSatelliteProvider` otherwise. The current rate limiter is
process-local; use Redis for multi-instance deployment.

### Running Tests
```bash
pytest
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
