# 🤝 Contributing to AURORA

We're building humanity's multi-planetary infrastructure. We'd love your help!

## Code of Conduct

Be respectful, inclusive, and professional. We're all working toward the same goal: making humanity multi-planetary.

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with PostGIS
- Docker & Docker Compose (recommended)
- Git

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/sybertoooth7-lgtm/AURORA.git
cd AURORA

# Backend setup
cd backend
cp .env.example .env

# Using Docker (Recommended)
docker-compose up -d

# Using Local Environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b bugfix/your-bug-name
```

### 2. Make Changes

Follow these guidelines:

- Write clean, readable code
- Add type hints to Python code
- Document complex logic with comments
- Follow PEP 8 style guidelines

### 3. Write Tests

```bash
# Add tests for new features
pytest tests/

# Check coverage
pytest --cov=app tests/
```

### 4. Code Quality

```bash
# Format code
black .
isort .

# Check style
flake8 .
mypy .

# Run all checks
make lint  # if Makefile exists
```

### 5. Commit & Push

```bash
git add .
git commit -m "Add/Fix: Brief description of changes"
git push origin feature/your-feature-name
```

### 6. Create Pull Request

- Go to GitHub and create a PR
- Link any related issues
- Describe what and why (not how)
- Request reviewers

## Commit Message Guidelines

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Test additions/changes
- `ci`: CI/CD changes
- `chore`: Build, dependencies, etc.

### Example

```
feat(analysis): Add vegetation stress detection

Implement NDVI-based vegetation stress analysis using satellite imagery.
Supports Sentinel-2 and Landsat imagery.

Fixes #123
```

## Areas for Contribution

### Backend
- [ ] API endpoints
- [ ] Database models
- [ ] AI/ML modules
- [ ] Error handling
- [ ] Authentication/Authorization
- [ ] Performance optimization
- [ ] Documentation

### Frontend (Coming Soon)
- [ ] Web UI (React/Next.js)
- [ ] Mobile app (Flutter)
- [ ] Data visualization
- [ ] User experience

### ML/AI
- [ ] Computer vision models
- [ ] Vegetation stress detection
- [ ] Land change detection
- [ ] Climate analysis
- [ ] Robotics algorithms

### Infrastructure
- [ ] DevOps
- [ ] CI/CD pipelines
- [ ] Containerization
- [ ] Kubernetes deployment
- [ ] Monitoring & logging

### Documentation
- [ ] API documentation
- [ ] Setup guides
- [ ] Architecture docs
- [ ] Code examples
- [ ] User guides

## Project Structure

```
backend/
├── app/
│   ├── models/        # Database models (edit here)
│   ├── schemas/       # API schemas (edit here)
│   ├── routes/        # API endpoints (edit here)
│   ├── ai/            # ML modules (edit here)
│   ├── config.py      # Configuration
│   └── database.py    # Database setup
├── tests/             # Test files (add tests here)
├── main.py            # Application entry point
├── requirements.txt   # Dependencies
└── README.md          # Backend documentation
```

## Common Tasks

### Add a New API Endpoint

1. Create schema in `app/schemas/`
2. Create model in `app/models/` (if needed)
3. Create route in `app/routes/`
4. Add route to `app/routes/__init__.py`
5. Include router in `main.py`
6. Write tests

### Add a New Database Model

1. Create model file in `app/models/`
2. Add to `app/models/__init__.py`
3. Create migration (if using Alembic)
4. Add related schemas
5. Add API endpoints

### Add an AI/ML Feature

1. Create module in `app/ai/`
2. Import in analysis logic
3. Add API endpoint if user-facing
4. Write tests
5. Document parameters & outputs

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_analysis.py

# Run specific test
pytest tests/test_analysis.py::test_create_analysis

# Run with coverage
pytest --cov=app tests/

# Run with verbose output
pytest -v
```

### Test Template

```python
import pytest
from fastapi.testclient import TestClient
from main import app
from app.database import get_db

client = TestClient(app)

def test_health_check():
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
```

## Documentation

### Code Comments

```python
def analyze_vegetation_stress(image: np.ndarray) -> Dict[str, float]:
    """
    Analyze vegetation stress from satellite image using NDVI.
    
    Args:
        image: NumPy array of satellite image data
    
    Returns:
        Dictionary with:
        - stress_score: Float 0-1 indicating stress level
        - affected_percentage: Percentage of area affected
        - confidence: Confidence in analysis 0-1
    """
    # NDVI calculation
    nir = image[3]  # Near-infrared band
    red = image[0]  # Red band
    ndvi = (nir - red) / (nir + red + 1e-8)
    return {"stress_score": float(ndvi.mean())}
```

### README Updates

When adding features:
1. Update backend README with new endpoint
2. Add to API documentation
3. Include usage examples
4. Document parameters & responses

## Performance Guidelines

- Avoid N+1 queries (use eager loading)
- Cache frequently accessed data
- Use database indexes for filters
- Profile slow operations
- Optimize AI/ML inference

## Security Guidelines

- Never commit secrets/API keys
- Validate all user input
- Use parameterized queries
- Implement rate limiting
- Use HTTPS in production
- Hash passwords securely
- Follow OWASP guidelines

## Release Process

1. Update version in `pyproject.toml` or similar
2. Update CHANGELOG.md
3. Create git tag: `git tag -a v0.1.0 -m "Version 0.1.0"`
4. Push tag: `git push origin v0.1.0`
5. Create GitHub release

## Getting Help

- Check existing issues & PRs
- Read documentation
- Ask in discussions
- Contact team: info@aurora-space.com

## Recognition

Contributors will be recognized in:
- README.md
- CONTRIBUTORS.md
- Release notes
- Project acknowledgments

---

**Thank you for contributing to AURORA! Together, we're building humanity's multi-planetary future.** 🚀
