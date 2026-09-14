"""End-to-end smoke test for demo mode (``ENABLE_DEMO_MODE``).

Booting the app in-process is impossible here: ``get_settings`` is
``lru_cache``d and the SQLAlchemy engine is built at module import time, so
the flag cannot be flipped after ``main`` has been imported. Instead this
test launches ``uvicorn main:app`` as a subprocess with the flag set and
drives the full platform lifecycle -- register -> token -> AI inference ->
insurance trigger-check -> robotics inspect -> analysis listing -- all on an
in-memory SQLite database with zero Postgres/Redis.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def demo_server():
    port = _free_port()
    env = os.environ.copy()
    env["ENABLE_DEMO_MODE"] = "true"
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 40
        while True:
            if proc.poll() is not None:
                pytest.fail("demo uvicorn process exited before becoming healthy")
            try:
                response = httpx.get(f"{base}/health/", timeout=5)
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline:
                pytest.fail("demo server did not become healthy in time")
            time.sleep(0.5)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)


def test_demo_mode_serves_the_full_platform(demo_server):
    with httpx.Client(base_url=demo_server, timeout=30) as client:
        # Public metadata endpoints boot fine with no infra.
        health = client.get("/health/").json()
        assert health["status"] == "healthy"
        caps = client.get("/system/capabilities")
        assert caps.status_code == 200
        assert "version" in caps.json()
        pipelines = client.get("/ai/pipelines").json()
        all_handles = [h for entry in pipelines for h in entry["handles"]]
        assert "vegetation_stress" in all_handles
        defaults = client.get("/insurance/defaults").json()
        assert defaults["analysis_type"] == "insurance_index"

        # Register + authenticate.
        register = client.post(
            "/auth/register",
            json={
                "email": "demo@aurora.space",
                "username": "demo_user",
                "password": "demo-pass-123",
                "full_name": "Demo User",
            },
        )
        assert register.status_code == 201
        token = client.post(
            "/auth/token",
            json={"username": "demo_user", "password": "demo-pass-123"},
        ).json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        area = {"latitude": 31.2304, "longitude": 121.4737, "radius_km": 5.0}

        # AI inference (vegetation stress) -- synchronously persisted.
        infer = client.post(
            "/ai/infer",
            headers=auth,
            json={"analysis_type": "vegetation_stress", "use_history": False, **area},
        )
        assert infer.status_code == 200, infer.text
        infer_body = infer.json()
        assert infer_body["created_analysis_id"] > 0
        assert infer_body["result"]["simulated"] is True
        assert infer_body["result"]["provenance"] == "simulated"

        # Insurance trigger-check -- honest simulated provenance.
        trigger = client.post(
            "/insurance/trigger-check",
            headers=auth,
            json={"sum_insured_usd": 250000, "use_history": False, **area},
        )
        assert trigger.status_code == 200, trigger.text
        trigger_body = trigger.json()
        assert trigger_body["data_quality"] == "simulated"
        assert trigger_body["analysis_id"] > 0

        # Robotics inspect -- fuses a flight into the report.
        flight = client.post(
            "/robotics/flights/demo-flight-1/telemetry",
            headers=auth,
            json={"battery_percent": 87.5, "gps_accuracy_m": 1.2},
        )
        assert flight.status_code == 200
        inspect = client.post(
            "/robotics/inspect",
            headers=auth,
            json={"use_history": False, "flight_id": "demo-flight-1", **area},
        )
        assert inspect.status_code == 200, inspect.text
        inspect_body = inspect.json()
        assert inspect_body["flight_health"] is not None
        assert len(inspect_body["combined_report"]) >= 2
        assert inspect_body["result"]["simulated"] is True

        # All three persisted runs appear in the user's analysis list.
        analyses = client.get("/analysis/", headers=auth)
        assert analyses.status_code == 200
        types = {entry["analysis_type"] for entry in analyses.json()}
        assert {"vegetation_stress", "insurance_index", "robotics_inspection"} <= types

        # The async job path also completes inline (demo queue = synchronous).
        queued = client.post("/analysis/", headers=auth, json={"analysis_type": "vegetation_stress", "description": "queued", **area})
        assert queued.status_code == 200, queued.text
        queued_id = queued.json()["id"]
        detail = client.get(f"/analysis/{queued_id}", headers=auth).json()
        assert detail["status"] == "completed"
