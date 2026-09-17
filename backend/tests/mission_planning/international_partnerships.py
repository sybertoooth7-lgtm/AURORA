"""Partner and agreement tracking for Mission Planning's International
Partnerships function.

Business-ops domain model (see the package README for why this sits
differently than scheduling.py): who AURORA has a relationship with,
what kind, and whether any agreement governing it is about to lapse.
Not wired to a live route yet.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class PartnerType(Enum):
    REGULATORY = "regulatory"
    DATA = "data"
    DISTRIBUTION = "distribution"
    RESEARCH = "research"


class PartnerStatus(Enum):
    PROSPECTIVE = "prospective"
    ACTIVE = "active"
    LAPSED = "lapsed"


@dataclass
class Agreement:
    partner_name: str
    scope: str
    effective_at: datetime
    expires_at: datetime | None = None
    data_sharing_allowed: bool = False

    def is_active(self, now: datetime) -> bool:
        if now < self.effective_at:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def expires_within(self, now: datetime, days: int) -> bool:
        if self.expires_at is None or not self.is_active(now):
            return False
        return (self.expires_at - now).days <= days


@dataclass
class Partner:
    name: str
    jurisdiction: str
    partner_type: PartnerType
    status: PartnerStatus = PartnerStatus.PROSPECTIVE
    agreements: list[Agreement] = field(default_factory=list)


class PartnershipRegistry:
    """Every partner relationship and its governing agreements."""

    def __init__(self) -> None:
        self._partners: dict[str, Partner] = {}

    def register(self, partner: Partner) -> None:
        self._partners[partner.name] = partner

    def get(self, name: str) -> Partner | None:
        return self._partners.get(name)

    def add_agreement(self, partner_name: str, agreement: Agreement) -> None:
        partner = self._require(partner_name)
        partner.agreements.append(agreement)
        partner.status = PartnerStatus.ACTIVE

    def active_partners(self, now: datetime) -> list[Partner]:
        return [
            p for p in self._partners.values()
            if any(a.is_active(now) for a in p.agreements)
        ]

    def expiring_agreements(
        self, now: datetime, within_days: int = 30
    ) -> list[tuple[str, Agreement]]:
        out: list[tuple[str, Agreement]] = []
        for partner in self._partners.values():
            for agreement in partner.agreements:
                if agreement.expires_within(now, within_days):
                    out.append((partner.name, agreement))
        return out

    def _require(self, name: str) -> Partner:
        partner = self._partners.get(name)
        if partner is None:
            raise KeyError(f"Unknown partner '{name}'")
        return partner
