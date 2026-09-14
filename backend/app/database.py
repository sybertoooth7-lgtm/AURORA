"""
AURORA Database Configuration
PostgreSQL + PostGIS for geospatial data; in-memory SQLite in demo mode.
"""

from sqlalchemy import Text, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings

settings = get_settings()


def demo_mode() -> bool:
    """True when the platform runs as a self-contained in-memory demo.

    Uses an in-memory SQLite database (shared single connection via
    StaticPool) instead of Postgres/PostGIS, so the app boots with zero
    external infrastructure. Every other code path -- routes, AI pipelines,
    satellite providers, auth -- is identical to the deployed platform.
    """
    return get_settings().ENABLE_DEMO_MODE


# Create engine
if demo_mode():
    # `sqlite://` (no filename) + StaticPool = one connection shared by all
    # sessions, so the whole process sees a single in-memory database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.SQLALCHEMY_ECHO,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
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


def geometry_type():
    """Return the SQLAlchemy column type for geometry fields.

    In production this is a PostGIS Geometry column; in demo mode plain
    Text (geoalchemy2 is never imported when demo is enabled -- its global
    SQLite dialect patches would break the in-memory database).
    """
    if demo_mode():
        return Text()
    from geoalchemy2 import Geometry

    return Geometry("POLYGON", srid=4326)


def area_geometry(polygon_wkt: str):
    """Store a search-area polygon in the database.

    On Postgres this goes in as a PostGIS geometry; in demo mode the
    geometry column is plain text, so bind the WKT string directly.
    """
    if demo_mode():
        return polygon_wkt
    from geoalchemy2.elements import WKTElement

    return WKTElement(polygon_wkt, srid=4326)


def init_demo_schema() -> None:
    """Create the full schema in-memory (demo mode only).

    Migrations remain the source of truth for Postgres deployments (the
    demo database is ephemeral and never returned to, so create_all is fine
    here and nowhere else).
    """
    if not demo_mode():
        raise RuntimeError("init_demo_schema() is only valid in demo mode")
    Base.metadata.create_all(engine)


# Enable PostGIS extension (demo mode skips this -- the PostGIS listener
# is only registered for the Postgres engine, and geoalchemy2 is never
# imported in demo mode).
if not demo_mode():

    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
            dbapi_connection.commit()
            cursor.close()
        except Exception as e:
            print(f"PostGIS extension already exists or error: {e}")
