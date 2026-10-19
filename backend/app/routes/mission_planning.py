"""Mission Planning endpoints: schedule construction and data readiness.

``app.mission_planning.scheduling`` is a greedy list scheduler: deterministic,
explainable about why a task could not be placed, and not a global optimiser.
``app.mission_planning.data_infrastructure`` was written as domain logic with
nothing feeding it; here it is fed from the platform's own job counters, so the
answer to "why did this analysis fail" can start with infrastructure state
instead of guessing. The status it reports is inferred from what the platform
observed about itself today -- it is not a provider health probe.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.ai.base import Provenance
from app.exceptions import ValidationFailedError
from app.job_metrics import COUNTER_NAMES, counter
from app.mission_planning.data_infrastructure import (
    DataInfrastructureRegistry,
    DataSource,
    SourceStatus,
)
from app.mission_planning.scheduling import (
    MissionScheduler,
    ResourceBudget,
    Task,
    TaskPriority,
)
from app.models.user import User
from app.satellite.providers import DemoSatelliteProvider, get_satellite_provider
from app.schemas.mission_planning import (
    DataReadinessResponse,
    DataSourceReadiness,
    RejectedTask,
    ScheduledTaskOut,
    ScheduleRequest,
    ScheduleResponse,
)
from app.security import get_current_user
from app.spacecraft.mission import ContactWindow

router = APIRouter(prefix="/mission-planning", tags=["Mission Planning"])

_SCHEDULE_LIMITATIONS = [
    "greedy list scheduler: not optimal in the bin-packing sense, so a slot a "
    "global optimiser would have filled can be left empty",
    "resources are treated as flat capacities over the whole horizon; there is "
    "no setup, turnaround or travel time between tasks",
    "a task with an untracked resource requirement is treated as unbounded",
    "contact windows are taken as given; nothing here propagates them",
]


@router.post("/schedule", response_model=ScheduleResponse)
def build_schedule(
    request: ScheduleRequest,
    current_user: User = Depends(get_current_user),
):
    """Place tasks against resource budgets and contact windows, priority first."""
    scheduler = MissionScheduler()
    for budget in request.budgets:
        scheduler.add_budget(
            ResourceBudget(name=budget.name, capacity=budget.capacity, unit=budget.unit)
        )
    for window in request.contact_windows:
        scheduler.add_contact_window(
            ContactWindow(
                ground_station=window.ground_station,
                start_s=window.start_s,
                end_s=window.end_s,
                max_elevation_deg=window.max_elevation_deg,
                slant_range_km=window.slant_range_km,
            )
        )

    try:
        tasks = [
            Task(
                id=entry.id,
                name=entry.name or entry.id,
                priority=TaskPriority[entry.priority.upper()],
                earliest_start_s=entry.earliest_start_s,
                latest_finish_s=entry.latest_finish_s,
                duration_s=entry.duration_s,
                resource_requirements=dict(entry.resource_requirements),
                requires_contact=entry.requires_contact,
            )
            for entry in request.tasks
        ]
    except ValueError as exc:  # engine validates the window/duration relationship
        raise ValidationFailedError(str(exc)) from exc

    scheduled, conflicts = scheduler.build_schedule(tasks)
    scheduled.sort(key=lambda item: (item.start_s, item.task.id))

    return ScheduleResponse(
        provenance=Provenance.SIMULATED,
        scheduled=[
            ScheduledTaskOut(
                id=item.task.id,
                name=item.task.name,
                priority=item.task.priority.name.lower(),
                start_s=round(item.start_s, 3),
                end_s=round(item.end_s, 3),
                requires_contact=item.task.requires_contact,
            )
            for item in scheduled
        ],
        conflicts=[
            RejectedTask(
                id=conflict.task.id,
                name=conflict.task.name,
                priority=conflict.task.priority.name.lower(),
                reason=conflict.reason,
            )
            for conflict in conflicts
        ],
        window_start_s=min(task.earliest_start_s for task in tasks),
        window_end_s=max(task.latest_finish_s for task in tasks),
        model_limitations=_SCHEDULE_LIMITATIONS,
    )


@router.get("/data-readiness", response_model=DataReadinessResponse)
def data_readiness(current_user: User = Depends(get_current_user)):
    """Whether it is safe to schedule new monitoring work, per data source.

    The one honest signal the platform has about its providers today is how
    their analysis jobs ended, so that is what sets each status: all jobs
    completed is healthy, a mix is degraded, nothing succeeding is down, and a
    day with no jobs is unknown rather than assumed fine.
    """
    provider = get_satellite_provider()
    counters = {name: counter(name) for name in COUNTER_NAMES}
    attempted = counters["completed"] + counters["failed"]

    if attempted == 0:
        observed = SourceStatus.UNKNOWN
    elif counters["completed"] == 0:
        observed = SourceStatus.DOWN
    elif counters["failed"] == 0:
        observed = SourceStatus.HEALTHY
    else:
        observed = SourceStatus.DEGRADED

    live = not isinstance(provider, DemoSatelliteProvider)
    sources = [
        DataSource(
            name="sentinel-2-l2a" if live else "demo",
            provider=type(provider).__name__,
            status=observed,
            last_checked_at=datetime.now(UTC),
        )
    ]
    if not live:
        # Without Copernicus credentials the live source cannot serve anything,
        # which is a scheduling fact rather than an unprobed one.
        sources.append(
            DataSource(
                name="sentinel-2-l2a",
                provider="SentinelHubProvider",
                status=SourceStatus.DOWN,
                last_checked_at=datetime.now(UTC),
            )
        )

    registry = DataInfrastructureRegistry()
    for source in sources:
        registry.register(source)
    schedulable = {source.name for source in registry.schedulable_sources()}
    report = registry.readiness_report()

    return DataReadinessResponse(
        provenance=Provenance.REAL,
        stage="platform_telemetry",
        overall=report["overall"],
        basis=(
            "inferred from today's analysis job outcomes "
            f"({counters['completed']} completed / {counters['failed']} failed); "
            "no provider health probe and no upstream quota telemetry"
        ),
        sources=[
            DataSourceReadiness(
                name=source.name,
                provider=source.provider,
                status=source.status.value,
                quota_used=source.quota_used,
                quota_limit=source.quota_limit,
                quota_fraction_used=source.quota_fraction_used,
                schedulable=source.name in schedulable,
            )
            for source in sources
        ],
        observations=counters,
        model_limitations=[
            "a provider with no jobs attempted today reads as unknown, not healthy",
            "job failures are attributed to the active provider wholesale: a "
            "pipeline bug and a provider outage look the same here",
            "upstream processing-unit usage is not tracked, so the quota fields "
            "read as zero and unknown",
        ],
    )
