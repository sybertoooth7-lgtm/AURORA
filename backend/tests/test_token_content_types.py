"""Regression tests for how ``POST /auth/token`` reads its body.

The endpoint documented a JSON credentials model, so every other body the same
route can be handed -- an OAuth2 form post, a text body, malformed or empty
JSON -- reached the request-validation error path with the raw bytes as the
offending ``input``. Serialising that error raised again, and the client got a
bare 500 with no CORS headers instead of a 422 it could read.
"""

import pytest
from fastapi.testclient import TestClient

from app.queue import get_redis
from main import app

PASSWORD = "correcthorsebatterystaple"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_state():
    redis = get_redis()
    for pattern in ("auth:*", "quota:*", "ratelimit:*"):
        keys = redis.keys(pattern)
        if keys:
            redis.delete(*keys)
    yield
    keys = redis.keys("auth:*") + redis.keys("quota:*")
    if keys:
        redis.delete(*keys)


def _register(client, username):
    return client.post(
        "/auth/register",
        json={"email": f"{username}@test.com", "username": username, "password": PASSWORD},
    )


def test_form_encoded_login_is_a_readable_422(client):
    """``/auth/token`` takes JSON, not an OAuth2 form post.

    A standard form client (Swagger's Authorize button among them) used to get
    a bare 500 with no CORS headers, because the unparsed body became the
    ``input`` of the validation error and the error itself could not be
    serialised.
    """
    assert _register(client, "formlogin").status_code == 201
    response = client.post(
        "/auth/token",
        data={"username": "formlogin", "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "http://localhost:5173"},
    )
    assert response.status_code == 422, response.text
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "errors" in response.json()


def test_rejected_body_is_never_echoed_back(client):
    """The body that failed to parse is a password; keep it out of the response."""
    response = client.post(
        "/auth/token",
        data={"username": "echo", "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert "echo" not in response.text


def test_json_login_still_works(client):
    _register(client, "jsonlogin")
    response = client.post("/auth/token", json={"username": "jsonlogin", "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"username=x&password=y", "text/plain"),
        (b"{ not json", "application/json"),
        (b"", "application/json"),
    ],
    ids=["text-body", "malformed-json", "empty-body"],
)
def test_unreadable_body_is_a_readable_error(client, body, content_type):
    response = client.post(
        "/auth/token", content=body, headers={"Content-Type": content_type, "Origin": "http://localhost:5173"}
    )
    assert response.status_code in (401, 422), response.text
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.text


@pytest.mark.parametrize(
    "body",
    [
        {"username": 12345, "password": PASSWORD},
        {"username": "x" * 200, "password": PASSWORD},
        {},
    ],
    ids=["wrong-type", "too-long", "missing-fields"],
)
def test_invalid_credentials_shape_is_422_not_500(client, body):
    response = client.post(
        "/auth/token", json=body, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 422, response.text
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "errors" in response.json()


def test_the_handler_fix_is_global_not_route_specific(client):
    """Any route whose JSON body cannot be parsed took the same fall.

    Asserted on ``/auth/register`` because it is the other endpoint a caller
    reaches before they have a token to authenticate with.
    """
    response = client.post(
        "/auth/register",
        content=b"username=regform&password=whatever1234",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": "http://localhost:5173"},
    )
    assert response.status_code == 422, response.text
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "whatever1234" not in response.text
