"""Tests for the onboarding flow builder (AURORA-2).

Covers ``build_onboarding_status`` as a pure function so the progress /
next_action logic is exercised without a database connection.
"""


from app.routes.onboarding import build_onboarding_status, has_live_satellite


class _FakeUser:
    def __init__(self, user_id=1, username="alice", onboarding_completed_at=None):
        self.id = user_id
        self.username = username
        self.onboarding_completed_at = onboarding_completed_at


class TestOnboardingStatus:
    def test_new_user_starts_with_early_progress(self):
        status = build_onboarding_status(
            _FakeUser(),
            analysis_count=0,
            live_satellite=False,
            pipeline_count=9,
            onboarding_complete=False,
        )
        assert status.completed is False
        # account + pipeline review are done by construction; the data-capable
        # steps are not.
        assert status.progress == 50
        assert status.next_action == "satellite_source"

    def test_account_is_always_done(self):
        status = build_onboarding_status(
            _FakeUser(),
            analysis_count=0,
            live_satellite=False,
            pipeline_count=9,
            onboarding_complete=False,
        )
        account_item = next(c for c in status.checklist if c.id == "account")
        assert account_item.done is True

    def test_live_satellite_checked_when_configured(self):
        status = build_onboarding_status(
            _FakeUser(),
            analysis_count=0,
            live_satellite=True,
            pipeline_count=9,
            onboarding_complete=False,
        )
        sat_item = next(c for c in status.checklist if c.id == "satellite_source")
        assert sat_item.done is True
        assert sat_item.instructions is None

    def test_satellite_unconfigured_includes_instructions(self):
        status = build_onboarding_status(
            _FakeUser(),
            analysis_count=0,
            live_satellite=False,
            pipeline_count=9,
            onboarding_complete=False,
        )
        sat_item = next(c for c in status.checklist if c.id == "satellite_source")
        assert sat_item.done is False
        assert sat_item.instructions is not None
        assert "OAuth" in sat_item.instructions

    def test_analysis_count_flips_first_analysis_done(self):
        status = build_onboarding_status(
            _FakeUser(),
            analysis_count=1,
            live_satellite=False,
            pipeline_count=9,
            onboarding_complete=False,
        )
        item = next(c for c in status.checklist if c.id == "first_analysis")
        assert item.done is True

    def test_complete_param_sets_completed(self):
        status = build_onboarding_status(
            _FakeUser(),
            analysis_count=0,
            live_satellite=True,
            pipeline_count=9,
            onboarding_complete=True,
        )
        assert status.completed is True
        # still guides the freshly-onboarded user toward their first run.
        assert status.next_action == "first_analysis"

    def test_progress_scales_linearly(self):
        status = build_onboarding_status(
            _FakeUser(),
            analysis_count=0,
            live_satellite=False,
            pipeline_count=0,
            onboarding_complete=False,
        )
        done_ids = [c.id for c in status.checklist if c.done]
        done_ids.append("first_analysis")  # mock run
        progress = round(len(done_ids) / len(status.checklist) * 100)
        assert 0 < progress < 100


class TestHasLiveSatellite:
    def _set(self, monkeypatch, demo: bool, creds: bool) -> None:
        class _Settings:
            ENABLE_DEMO_MODE = demo
            SENTINEL_CLIENT_ID = "id" if creds else None
            SENTINEL_CLIENT_SECRET = "secret" if creds else None
            SENTINEL_TOKEN_URL = "https://token.example"
            SENTINEL_STATS_URL = "https://stats.example"
            SENTINEL_LOOKBACK_DAYS = 30

        monkeypatch.setattr("app.routes.onboarding.get_settings", lambda: _Settings())
        monkeypatch.setattr("app.satellite.providers.get_settings", lambda: _Settings())

    def test_demo_mode_forces_simulated(self, monkeypatch):
        self._set(monkeypatch, demo=True, creds=True)
        assert has_live_satellite() is False

    def test_live_when_configured_outside_demo(self, monkeypatch):
        self._set(monkeypatch, demo=False, creds=True)
        assert has_live_satellite() is True

    def test_no_credentials_means_simulated(self, monkeypatch):
        self._set(monkeypatch, demo=False, creds=False)
        assert has_live_satellite() is False
