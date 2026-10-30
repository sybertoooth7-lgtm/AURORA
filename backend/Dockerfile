FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Apply pending Alembic migrations, then start the API. Migrations run once
# here rather than in app startup code so multiple API replicas don't race
# each other applying schema changes. The migration step is per container,
# which is safe because Alembic serialises on its version table.
#
# API_WORKERS controls uvicorn's process count inside this container. Each
# worker holds its own DB pool, so keep
# `API_WORKERS * (DB_POOL_SIZE + DB_MAX_OVERFLOW)` plus worker processes below
# the database's max_connections. `exec` makes uvicorn PID 1 so it receives
# SIGTERM directly and drains in-flight requests on deploy.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers ${API_WORKERS:-4} --proxy-headers --forwarded-allow-ips ${FORWARDED_ALLOW_IPS:-127.0.0.1}"]
