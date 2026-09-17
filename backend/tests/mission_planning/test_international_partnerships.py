from datetime import UTC, datetime, timedelta

from app.mission_planning.international_partnerships import (
    Agreement,
    Partner,
    PartnershipRegistry,
    PartnerStatus,
    PartnerType,
)


def test_agreement_is_active_within_its_effective_window():
    now = datetime.now(UTC)
    agreement = Agreement(
        partner_name="Kenya Space Agency", scope="data-sharing",
        effective_at=now - timedelta(days=1), expires_at=now + timedelta(days=30),
    )
    assert agreement.is_active(now) is True


def test_agreement_is_not_active_before_effective_or_after_expiry():
    now = datetime.now(UTC)
    not_yet = Agreement(partner_name="p", scope="s", effective_at=now + timedelta(days=1))
    expired = Agreement(partner_name="p", scope="s", effective_at=now - timedelta(days=10),
                         expires_at=now - timedelta(days=1))
    assert not_yet.is_active(now) is False
    assert expired.is_active(now) is False


def test_expires_within_flags_agreements_close_to_lapsing():
    now = datetime.now(UTC)
    soon = Agreement(partner_name="p", scope="s", effective_at=now - timedelta(days=1),
                      expires_at=now + timedelta(days=10))
    far = Agreement(partner_name="p", scope="s", effective_at=now - timedelta(days=1),
                     expires_at=now + timedelta(days=200))
    assert soon.expires_within(now, days=30) is True
    assert far.expires_within(now, days=30) is False


def test_registering_an_agreement_activates_the_partner():
    now = datetime.now(UTC)
    registry = PartnershipRegistry()
    registry.register(Partner(name="KSA", jurisdiction="Kenya", partner_type=PartnerType.REGULATORY))

    registry.add_agreement("KSA", Agreement(
        partner_name="KSA", scope="data-sharing", effective_at=now - timedelta(days=1),
    ))

    assert registry.get("KSA").status == PartnerStatus.ACTIVE


def test_active_partners_excludes_partners_with_no_active_agreement():
    now = datetime.now(UTC)
    registry = PartnershipRegistry()
    registry.register(Partner(name="active-partner", jurisdiction="Kenya", partner_type=PartnerType.DATA))
    registry.register(Partner(name="prospective-partner", jurisdiction="Kenya", partner_type=PartnerType.DATA))
    registry.add_agreement("active-partner", Agreement(
        partner_name="active-partner", scope="x", effective_at=now - timedelta(days=1),
    ))

    active = registry.active_partners(now)

    assert [p.name for p in active] == ["active-partner"]


def test_expiring_agreements_reports_partner_and_agreement_pairs():
    now = datetime.now(UTC)
    registry = PartnershipRegistry()
    registry.register(Partner(name="p", jurisdiction="Kenya", partner_type=PartnerType.DISTRIBUTION))
    registry.add_agreement("p", Agreement(
        partner_name="p", scope="x", effective_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=5),
    ))

    expiring = registry.expiring_agreements(now, within_days=30)

    assert len(expiring) == 1
    assert expiring[0][0] == "p"


def test_unknown_partner_raises_on_add_agreement():
    import pytest

    registry = PartnershipRegistry()
    with pytest.raises(KeyError):
        registry.add_agreement("nope", Agreement(
            partner_name="nope", scope="x", effective_at=datetime.now(UTC),
        ))
