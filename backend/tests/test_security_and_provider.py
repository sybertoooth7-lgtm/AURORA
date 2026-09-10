import pytest

from app.security import hash_password, verify_password
from app.schemas.user import UserCreate
from app.satellite.providers import DemoSatelliteProvider


def test_password_hash_round_trip():
    encoded = hash_password("correct horse battery staple")

    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_password_hash_rejects_oversized_input():
    with pytest.raises(ValueError):
        hash_password("a" * 513)


def test_registration_requires_password_strength():
    with pytest.raises(ValueError):
        UserCreate(
            email="person@example.com",
            username="person",
            password="weakpassword",
        )


def test_demo_provider_is_deterministic_for_an_area():
    provider = DemoSatelliteProvider()

    first = provider.fetch_latest(-1.2, 36.8, 10)
    second = provider.fetch_latest(-1.2, 36.8, 10)

    assert first.image_id == second.image_id
    assert first.ndvi == second.ndvi
    assert 0 <= first.cloud_coverage <= 0.25