# 🌌 AURORA

**Build the technologies and economic infrastructure that allow humanity to explore, inhabit and responsibly utilize the Solar System.**

Multi-planetary space technology company. AI + Robotics + Space infrastructure.

## 🚀 Vision

Make humanity a multi-planetary civilization and develop intelligent infrastructure capable of operating across multiple worlds.

## 🏗️ Architecture

```
AURORA (Headquarters: Nairobi, Kenya)
│
├── AI Division
│   ├── Space Intelligence Platform
│   ├── Geospatial Analytics
│   ├── Autonomous Systems
│   └── Multi-planetary AI
│
├── Robotics Division
│   ├── Agricultural Robots
│   ├── Inspection Systems
│   ├── Autonomous Vehicles
│   └── Orbital Robotics (Future)
│
├── Space Division
│   ├── Earth Observation
│   ├── Satellite Constellation
│   ├── CubeSat Technology
│   └── Deep Space Infrastructure (Future)
│
└── Operations
    ├── Mission Planning
    ├── Data Infrastructure
    ├── Customer Support
    └── International Partnerships
```

## 📊 Current Focus (2026)

### Phase 1: Earth Revenue (Q3–Q4 2026)

Combined satellite imagery + AI + geospatial analytics into producible revenue lines:

- **Parametric agriculture insurance** — `InsuranceIndexPipeline` computes a crop-condition index and damage proxy; `POST /insurance/trigger-check` evaluates a parametric payout trigger for a field, with estimates clearly separated from settlements.
- **Robotics field services** — drones / ground robots publish MQTT-style telemetry into a bounded in-memory flight store; `POST /robotics/inspect` fuses the satellite-derived NDVI damage proxy with the robot's own flight health into a combined field report.
- **User onboarding flow** — guided checklist + first analysis, with honest next-step guidance that distinguishes simulated results from real satellite data.

Underpinning pipeline:

```
Satellite Imagery → AI Analysis → Geospatial Engine → Customer Dashboard → Revenue
```

## 📁 Repository Structure

```
AURORA/
├── .github/workflows/ci.yml    # CI: backend (PostGIS+Redis) + frontend build
├── aurora-frontend/            # React/Vite web app
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── routes/             # API endpoints
│   │   ├── ai/                 # Pipeline registry + 9 pipelines
│   │   ├── robotics/           # Robot core + flight telemetry store
│   │   ├── multiplanetary/     # 7-layer AI stack + mission ops
│   │   ├── space_resources/    # ISRU / resources program
│   │   ├── spacecraft/         # 3U CubeSat simulation
│   │   ├── config.py
│   │   └── database.py
│   ├── alembic/                # schema migrations
│   ├── main.py
│   ├── requirements.txt
│   ├── requirements-dev.txt    # ruff + mypy pinned for the CI gates
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── docs/                       # Architecture, API, strategy, roadmap
    ├── API.md
    ├── ARCHITECTURE.md
    ├── business_strategy.md
    ├── multiplanetary_ai_architecture.md
    └── space_resources_program.md
```

## 🚀 Quick Start

### Backend Development

```bash
cd backend

# Option 1: Docker (Recommended)
docker-compose up -d

# Option 2: Local
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

API will be available at: `http://localhost:8000`

**Health Check:**
```bash
curl http://localhost:8000/health/
```

**API Docs:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Frontend Development

```bash
cd aurora-frontend
npm install
npm run dev          # Vite dev server on http://localhost:5173
npm run build        # type-check (tsc) + production build
```

### Lint & type gates (enforced in CI)

```bash
cd backend
python -m ruff check .
python -m mypy app
python -m pytest tests/ -p no:warnings   # needs Postgres + Redis for the full suite
```

## 🎯 Product Strategy

### Year 1 (2026): Foundation
- [x] Company registration (Nairobi)
- [x] Backend architecture
- [x] Modular AI pipeline platform + capability registry
- [ ] MVP: Space Intelligence Platform
- [ ] First paying customers (agriculture insurance, field inspection)
- [ ] 5-12 person team

### Year 2 (2027): Commercial Traction
- [ ] Scale satellite analysis platform
- [ ] Launch autonomous robotics division
- [ ] Agriculture/insurance partnerships
- [ ] Series A funding

### Year 3 (2028): Hardware
- [ ] Space hardware R&D center (Konza)
- [ ] CubeSat technology demonstrator
- [ ] Advanced robotics lab

### Year 4-5 (2029-2030): Space Operations
- [ ] First spacecraft mission
- [ ] Orbital robotics
- [ ] In-space servicing capability

### 2030-2050: Lunar Infrastructure
- [ ] Lunar resource mapping
- [ ] Robotic mining demonstration
- [ ] Lunar propellant production

### 2050+: Mars & Beyond
- [ ] Mars infrastructure development
- [ ] Interstellar research division
- [ ] Multi-planetary civilization

## 🔧 Tech Stack

- **Backend**: FastAPI, Python 3.11+
- **Database**: PostgreSQL + PostGIS
- **Cache**: Redis (RQ worker, login lockout, token blocklist)
- **Satellite Data**: Copernicus Data Space Ecosystem (Sentinel Hub Statistical API), real Sentinel-2 NDVI; deterministic demo provider by default
- **API**: REST + OpenAPI (Swagger/ReDoc), JWT auth
- **Frontend**: React + Vite + TypeScript
- **Robotics**: telemetry ingestion + field inspection (prototype stage)
- **Quality**: ruff, mypy, pytest; GitHub Actions CI with PostGIS + Redis services
- **Containerization**: Docker + docker-compose
- **Cloud**: AWS/GCP (Production)

## 📚 Documentation

- [Backend README](./backend/README.md)
- [API Reference](./docs/API.md)
- [Architecture Guide](./docs/ARCHITECTURE.md)
- [Business Strategy](./docs/business_strategy.md)
- [Roadmap](./docs/ROADMAP.md)
- [Contributing Guide](./docs/CONTRIBUTING.md)

## 🤝 Contributing

We're building humanity's multi-planetary infrastructure. Join us!

See [CONTRIBUTING.md](./docs/CONTRIBUTING.md) for guidelines.

## 📝 License

MIT

## 👥 Team

**Founded in Nairobi, Kenya - 2026**

Building the space economy for Africa and the world.

## 📧 Contact

- Email: info@aurora-space.com

## 🌍 Strategic Partners

- Kenya Space Agency (KSA)
- Konza Technopolis
- Kenyan Universities
- International Space Organizations

---

**The most important thing: Your 2026 company should NOT look like the 2126 company.**

*In 2026: 10 engineers in Nairobi building AI-powered satellite intelligence and autonomous robotics.*

*Eventually: A civilization-scale organization operating across Earth, Moon, Mars and the wider Solar System.*

That's how we turn an enormous vision into something that can actually start **this year**.

🚀 **Let's build the future of space.**