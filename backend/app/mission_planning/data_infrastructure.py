"""Data infrastructure readiness tracking for Mission Planning.

Business-ops domain model, not a physics simulation (see the package
README for why this sits differently than scheduling.py): tracks the
health of the data sources AURORA's analyses actually depend on --
Sentinel Hub, the demo/fallback provider, future sources -- so Mission
Planning can tell whether it's safe to schedule new monitoring work
against a given source, and give an honest first answer to "why did this
analysis fail" that starts with infrastructure status rather than
guessing. Not wired to a live route or a real health-check loop yet;
this is the domain logic a future integration (e.g. periodically polling
app.satellite.providers) would update.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SourceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


@dataclass
class DataSource:
    name: str
    provider: str
    status: SourceStatus = SourceStatus.UNKNOWN
    last_checked_at: datetime | None = None
    quota_used: float = 0.0
    quota_limit: float | None = None

    @property
    def quota_fraction_used(self) -> float | None:
        if self.quota_limit is None or self.quota_limit <= 0:
            return None
        return min(1.0, self.quota_used / self.quota_limit)

    @property
    def is_schedulable(self) -> bool:
        """Whether Mission Planning should schedule new work against this
        source right now."""
        if self.status in (SourceStatus.DOWN, SourceStatus.UNKNOWN):
            return False
        fraction = self.quota_fraction_used
        return fraction is None or fraction < 1.0


class DataInfrastructureRegistry:
    """Every data source Mission Planning might schedule work against."""

    def __init__(self) -> None:
        self._sources: dict[str, DataSource] = {}

    def register(self, source: DataSource) -> None:
        self._sources[source.name] = source

    def get(self, name: str) -> DataSource | None:
        return self._sources.get(name)

    def update_status(self, name: str, status: SourceStatus, checked_at: datetime) -> None:
        source = self._require(name)
        source.status = status
        source.last_checked_at = checked_at

    def record_usage(self, name: str, quota_used: float) -> None:
        self._require(name).quota_used = quota_used

    def schedulable_sources(self) -> list[DataSource]:
        return [s for s in self._sources.values() if s.is_schedulable]

    def readiness_report(self) -> dict:
        sources = list(self._sources.values())
        if not sources:
            return {"overall": "unknown", "sources": []}
        healthy = sum(1 for s in sources if s.status == SourceStatus.HEALTHY)
        overall = (
            "healthy"
            if healthy == len(sources)
            else "degraded"
            if healthy > 0
            else "down"
        )
        return {
            "overall": overall,
            "sources": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "quota_fraction_used": s.quota_fraction_used,
                }
                for s in sources
            ],
        }

    def _require(self, name: str) -> DataSource:
        source = self._sources.get(name)
        if source is None:
            raise KeyError(f"Unknown data source '{name}'")
        return source
