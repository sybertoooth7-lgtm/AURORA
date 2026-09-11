"""
AURORA Database Configuration
PostgreSQL + PostGIS for geospatial data
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings

settings = get_settings()

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.SQLALCHEMY_ECHO,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for database sessions"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Enable PostGIS extension
@event.listens_for(engine, "connect")
def receive_connect(dbapi_connection, connection_record):
    """Enable PostGIS on connection"""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
        dbapi_connection.commit()
        cursor.close()
    except Exception as e:
        print(f"PostGIS extension already exists or error: {e}")
