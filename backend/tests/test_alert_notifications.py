"""Tests for the alert-email notification added in app.services.analysis_runner.

Tests _notify_user_of_alert directly against fake ORM-shaped objects
rather than depending on a specific satellite/pipeline combination
producing a severity above the alert threshold -- that's an
implementation detail of the pipelines, not of the notification logic
being tested here.
"""

from unittest.mock import patch

from app.database import SessionLocal
from app.models.user import User
from app.services.analysis_runner import _notify_user_of_alert


class _FakeAnalysis:
    def __init__(self, user_id, analysis_id=1, description=None, analysis_type_value="vegetation_stress"):
        self.id = analysis_id
        self.user_id = user_id

        class _T:
            value = analysis_type_value

        self.analysis_type = _T()
        self.description = description


class _FakeAlert:
    title = "Vegetation Stress Detected"
    description = "Severity 0.62 -- above the alert threshold."


def _make_real_user(username: str) -> int:
    from app.security import hash_password

    db = SessionLocal()
    try:
        user = User(
            email=f"{username}@test.com",
            username=username,
            hashed_password=hash_password("testpassword123"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def test_sends_email_with_expected_content():
    user_id = _make_real_user("notifyuser1")
    analysis = _FakeAnalysis(user_id, description="Naivasha flower farm")
    alert = _FakeAlert()

    db = SessionLocal()
    try:
        with patch("app.services.analysis_runner.send_alert_email") as mock_send:
            _notify_user_of_alert(db, analysis, alert)
    finally:
        db.close()

    mock_send.assert_called_once()
    kwargs = mock_send.call_args.kwargs
    assert kwargs["to"] == "notifyuser1@test.com"
    assert kwargs["area_name"] == "Naivasha flower farm"
    assert kwargs["alert_title"] == "Vegetation Stress Detected"
    assert "areas/1" in kwargs["dashboard_url"]


def test_falls_back_to_analysis_type_when_no_description():
    user_id = _make_real_user("notifyuser2")
    analysis = _FakeAnalysis(user_id, description=None, analysis_type_value="land_change")
    alert = _FakeAlert()

    db = SessionLocal()
    try:
        with patch("app.services.analysis_runner.send_alert_email") as mock_send:
            _notify_user_of_alert(db, analysis, alert)
    finally:
        db.close()

    assert mock_send.call_args.kwargs["area_name"] == "land change"


def test_missing_user_does_not_crash():
    analysis = _FakeAnalysis(user_id=999999)  # no such user
    alert = _FakeAlert()

    db = SessionLocal()
    try:
        with patch("app.services.analysis_runner.send_alert_email") as mock_send:
            _notify_user_of_alert(db, analysis, alert)  # should just no-op
    finally:
        db.close()

    mock_send.assert_not_called()


def test_email_failure_does_not_propagate():
    user_id = _make_real_user("notifyuser3")
    analysis = _FakeAnalysis(user_id)
    alert = _FakeAlert()

    db = SessionLocal()
    try:
        with patch(
            "app.services.analysis_runner.send_alert_email", side_effect=OSError("smtp down")
        ):
            _notify_user_of_alert(db, analysis, alert)  # should not raise
    finally:
        db.close()
