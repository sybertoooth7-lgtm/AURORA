from app.mission_planning.scheduling import (
    MissionScheduler,
    ResourceBudget,
    Task,
    TaskPriority,
)
from app.spacecraft.mission import ContactWindow


def test_schedules_non_conflicting_tasks_at_their_earliest_start():
    scheduler = MissionScheduler()
    tasks = [
        Task(id="a", name="A", priority=TaskPriority.NORMAL,
             earliest_start_s=0, latest_finish_s=1000, duration_s=100),
        Task(id="b", name="B", priority=TaskPriority.NORMAL,
             earliest_start_s=0, latest_finish_s=1000, duration_s=100),
    ]

    scheduled, conflicts = scheduler.build_schedule(tasks)

    assert conflicts == []
    assert {s.task.id: s.start_s for s in scheduled} == {"a": 0, "b": 0}


def test_higher_priority_gets_the_preferred_slot_on_scarce_resource():
    scheduler = MissionScheduler()
    scheduler.add_budget(ResourceBudget(name="downlink_mb", capacity=30, unit="MB"))
    tasks = [
        Task(id="low", name="Low priority", priority=TaskPriority.LOW,
             earliest_start_s=0, latest_finish_s=1000, duration_s=100,
             resource_requirements={"downlink_mb": 30}),
        Task(id="high", name="High priority", priority=TaskPriority.HIGH,
             earliest_start_s=0, latest_finish_s=1000, duration_s=100,
             resource_requirements={"downlink_mb": 30}),
    ]

    scheduled, conflicts = scheduler.build_schedule(tasks)
    by_id = {s.task.id: s.start_s for s in scheduled}

    assert conflicts == []
    assert by_id["high"] == 0  # high priority claims the preferred slot
    assert by_id["low"] == 100  # low priority bumped to right after


def test_resource_budget_is_never_oversubscribed():
    scheduler = MissionScheduler()
    scheduler.add_budget(ResourceBudget(name="power_w", capacity=10))
    tasks = [
        Task(id=f"t{i}", name=f"Task {i}", priority=TaskPriority.NORMAL,
             earliest_start_s=0, latest_finish_s=1000, duration_s=50,
             resource_requirements={"power_w": 6})
        for i in range(3)
    ]

    scheduled, conflicts = scheduler.build_schedule(tasks)

    # At most one 6W task can run at a time within a 10W budget -- check
    # no two scheduled tasks overlap while both consuming power_w.
    intervals = sorted((s.start_s, s.end_s) for s in scheduled)
    for (_s1, e1), (s2, _e2) in zip(intervals, intervals[1:], strict=False):
        assert e1 <= s2, "overlapping allocations exceed the power_w budget"


def test_requires_contact_only_schedules_within_a_contact_window():
    scheduler = MissionScheduler()
    scheduler.add_contact_window(
        ContactWindow(start_s=500, end_s=700, ground_station="Nairobi")
    )
    task = Task(
        id="downlink", name="Downlink session", priority=TaskPriority.NORMAL,
        earliest_start_s=0, latest_finish_s=1000, duration_s=100,
        requires_contact=True,
    )

    scheduled, conflicts = scheduler.build_schedule([task])

    assert conflicts == []
    assert 500 <= scheduled[0].start_s
    assert scheduled[0].end_s <= 700


def test_requires_contact_conflicts_when_no_window_registered():
    scheduler = MissionScheduler()
    task = Task(
        id="downlink", name="Downlink session", priority=TaskPriority.NORMAL,
        earliest_start_s=0, latest_finish_s=1000, duration_s=100,
        requires_contact=True,
    )

    scheduled, conflicts = scheduler.build_schedule([task])

    assert scheduled == []
    assert len(conflicts) == 1
    assert "ground-contact window" in conflicts[0].reason


def test_conflict_reason_when_requirement_exceeds_total_capacity():
    scheduler = MissionScheduler()
    scheduler.add_budget(ResourceBudget(name="power_w", capacity=5, unit="W"))
    task = Task(
        id="too-big", name="Too big", priority=TaskPriority.NORMAL,
        earliest_start_s=0, latest_finish_s=1000, duration_s=100,
        resource_requirements={"power_w": 10},
    )

    scheduled, conflicts = scheduler.build_schedule([task])

    assert scheduled == []
    assert "10W" in conflicts[0].reason
    assert "5W" in conflicts[0].reason


def test_task_rejects_a_duration_that_cannot_fit_its_window():
    import pytest

    with pytest.raises(ValueError, match="cannot fit"):
        Task(id="bad", name="Bad", priority=TaskPriority.NORMAL,
             earliest_start_s=0, latest_finish_s=100, duration_s=200)


def test_task_rejects_non_positive_duration():
    import pytest

    with pytest.raises(ValueError, match="must be positive"):
        Task(id="bad", name="Bad", priority=TaskPriority.NORMAL,
             earliest_start_s=0, latest_finish_s=100, duration_s=0)
