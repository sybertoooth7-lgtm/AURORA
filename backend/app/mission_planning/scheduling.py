"""Mission scheduling: task / resource / contact-window allocation.

Stage 0 simulation (same philosophy as app.spacecraft and app.robotics):
a deterministic, offline-testable scheduler with no hardware or live-route
dependency yet. Given a set of tasks (payload imaging requests, downlink
sessions, maneuvers -- anything with a time window, a duration, and
resource requirements), a set of resource budgets (power, downlink
bandwidth, storage), and optionally a set of ground-contact windows
(reuses app.spacecraft.mission.ContactWindow rather than redefining it),
produces a conflict-free schedule via priority-ordered greedy placement,
and reports exactly which tasks couldn't be placed and why.

This is the piece that actually deserves the name "mission planning" in
the engineering sense -- the org-chart items alongside it in this package
(data_infrastructure.py, customer_support.py, international_partnerships.py)
are a different kind of thing entirely; see the package README.
"""

from dataclasses import dataclass, field
from enum import Enum

from app.spacecraft.mission import ContactWindow


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class Task:
    """One schedulable unit of work.

    Times are seconds on whatever epoch the caller is using (matches
    app.spacecraft's convention of float seconds rather than datetimes,
    since mission timelines are usually reasoned about relative to launch
    or to "now", not wall-clock dates).
    """

    id: str
    name: str
    priority: TaskPriority
    earliest_start_s: float
    latest_finish_s: float
    duration_s: float
    resource_requirements: dict[str, float] = field(default_factory=dict)
    requires_contact: bool = False

    def __post_init__(self) -> None:
        if self.duration_s <= 0:
            raise ValueError(f"Task '{self.id}': duration_s must be positive")
        if self.earliest_start_s + self.duration_s > self.latest_finish_s:
            raise ValueError(
                f"Task '{self.id}': duration {self.duration_s}s cannot fit "
                f"between earliest_start_s and latest_finish_s"
            )


@dataclass
class ResourceBudget:
    name: str
    capacity: float
    unit: str = ""


@dataclass
class ScheduledTask:
    task: Task
    start_s: float

    @property
    def end_s(self) -> float:
        return self.start_s + self.task.duration_s


@dataclass
class SchedulingConflict:
    task: Task
    reason: str


@dataclass
class _Allocation:
    start_s: float
    end_s: float
    amount: float


class MissionScheduler:
    """Priority-ordered greedy scheduler over tasks, resource budgets, and
    (optionally) ground-contact windows.

    Not optimal in the bin-packing sense -- it's a greedy list scheduler,
    same trade-off real mission planning tools make: fast, deterministic,
    and easy to explain why a task landed where it did, at the cost of
    sometimes leaving a slot unused that a global optimizer would have
    filled. Ties are broken by earliest_start_s so results are stable.
    """

    def __init__(self) -> None:
        self._budgets: dict[str, ResourceBudget] = {}
        self._contact_windows: list[ContactWindow] = []

    def add_budget(self, budget: ResourceBudget) -> None:
        self._budgets[budget.name] = budget

    def add_contact_window(self, window: ContactWindow) -> None:
        self._contact_windows.append(window)

    def build_schedule(
        self, tasks: list[Task]
    ) -> tuple[list[ScheduledTask], list[SchedulingConflict]]:
        ordered = sorted(tasks, key=lambda t: (-t.priority.value, t.earliest_start_s))
        timeline: dict[str, list[_Allocation]] = {name: [] for name in self._budgets}
        scheduled: list[ScheduledTask] = []
        conflicts: list[SchedulingConflict] = []

        for task in ordered:
            start = self._find_slot(task, timeline)
            if start is None:
                conflicts.append(
                    SchedulingConflict(task=task, reason=self._conflict_reason(task))
                )
                continue
            scheduled.append(ScheduledTask(task=task, start_s=start))
            end = start + task.duration_s
            for resource, amount in task.resource_requirements.items():
                timeline.setdefault(resource, []).append(
                    _Allocation(start_s=start, end_s=end, amount=amount)
                )

        return scheduled, conflicts

    def _find_slot(self, task: Task, timeline: dict[str, list[_Allocation]]) -> float | None:
        for candidate in self._candidate_starts(task, timeline):
            if self._fits(task, candidate, timeline):
                return candidate
        return None

    def _candidate_starts(
        self, task: Task, timeline: dict[str, list[_Allocation]]
    ) -> list[float]:
        # Every point worth trying is either the task's own earliest start,
        # a moment some competing allocation frees up capacity, or (for
        # contact-bound tasks) the start of a contact window -- trying
        # anything else can't find a feasible slot this one would miss.
        times = {task.earliest_start_s}
        for resource in task.resource_requirements:
            for alloc in timeline.get(resource, []):
                if task.earliest_start_s < alloc.end_s <= task.latest_finish_s:
                    times.add(alloc.end_s)
        if task.requires_contact:
            for window in self._contact_windows:
                candidate = max(window.start_s, task.earliest_start_s)
                if candidate <= task.latest_finish_s:
                    times.add(candidate)
        return sorted(t for t in times if t + task.duration_s <= task.latest_finish_s)

    def _fits(self, task: Task, start_s: float, timeline: dict[str, list[_Allocation]]) -> bool:
        end_s = start_s + task.duration_s
        if task.requires_contact and not self._within_any_contact_window(start_s, end_s):
            return False
        for resource, amount in task.resource_requirements.items():
            budget = self._budgets.get(resource)
            if budget is None:
                continue  # unbounded/untracked resource -- don't block on it
            used = sum(
                alloc.amount
                for alloc in timeline.get(resource, [])
                if alloc.start_s < end_s and start_s < alloc.end_s  # overlap test
            )
            if used + amount > budget.capacity:
                return False
        return True

    def _within_any_contact_window(self, start_s: float, end_s: float) -> bool:
        return any(
            window.start_s <= start_s and end_s <= window.end_s
            for window in self._contact_windows
        )

    def _conflict_reason(self, task: Task) -> str:
        if task.requires_contact and not self._contact_windows:
            return "requires a ground-contact window but none are registered"
        for resource, amount in task.resource_requirements.items():
            budget = self._budgets.get(resource)
            if budget is not None and amount > budget.capacity:
                return (
                    f"requires {amount}{budget.unit} of '{resource}' but total "
                    f"capacity is only {budget.capacity}{budget.unit}"
                )
        return "no feasible slot within its time window given contention for shared resources"
