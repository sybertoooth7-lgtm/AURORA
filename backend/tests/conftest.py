"""Local test bootstrap.

In demo mode the app runs on an in-memory SQLite database whose schema is
created by the FastAPI lifespan during a normal boot. Tests drive the app
with ``TestClient(app)`` directly (no lifespan), so create the demo schema
once per session here when demo mode is active. In CI demo mode is off and
this is a no-op -- the real Postgres schema comes from
``alembic upgrade head`` in the workflow.
"""

import pytest

from app.database import Base, demo_mode, engine


@pytest.fixture(scope="session", autouse=True)
def _prepare_demo_database():
    if not demo_mode():
        yield
        return
    # Import every model module so each table registers on Base.metadata
    # before create_all -- ordering matters, so keep them explicit.
    import app.models.ai_model  # noqa: F401
    import app.models.alert  # noqa: F401
    import app.models.analysis  # noqa: F401
    import app.models.satellite_imagery  # noqa: F401
    import app.models.user  # noqa: F401

    Base.metadata.create_all(engine)
    yield
