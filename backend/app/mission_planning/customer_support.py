"""Support ticket tracking for Mission Planning's Customer Support function.

Business-ops domain model (see the package README for why this sits
differently than scheduling.py): ticket lifecycle, SLA tracking, and
escalation. Not wired to a live route or persisted anywhere yet -- this
is the domain logic a future /support API would sit on top of.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class TicketPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


# How long a ticket has before it's considered overdue, by priority. Not
# tied to any real support-team staffing plan yet -- these are reasonable
# placeholder targets, worth revisiting once there's an actual support
# function to hold to them.
_SLA_HOURS: dict[TicketPriority, int] = {
    TicketPriority.LOW: 72,
    TicketPriority.NORMAL: 24,
    TicketPriority.HIGH: 8,
    TicketPriority.URGENT: 2,
}


@dataclass
class SupportTicket:
    id: str
    customer_id: int
    subject: str
    priority: TicketPriority
    opened_at: datetime
    status: TicketStatus = TicketStatus.OPEN
    resolved_at: datetime | None = None

    @property
    def sla_due_at(self) -> datetime:
        return self.opened_at + timedelta(hours=_SLA_HOURS[self.priority])

    def is_overdue(self, now: datetime) -> bool:
        if self.status == TicketStatus.RESOLVED:
            return False
        return now > self.sla_due_at


class SupportQueue:
    """Tracks tickets and flags SLA breaches for escalation."""

    def __init__(self) -> None:
        self._tickets: dict[str, SupportTicket] = {}

    def open_ticket(self, ticket: SupportTicket) -> None:
        self._tickets[ticket.id] = ticket

    def get(self, ticket_id: str) -> SupportTicket | None:
        return self._tickets.get(ticket_id)

    def resolve(self, ticket_id: str, now: datetime) -> None:
        ticket = self._require(ticket_id)
        ticket.status = TicketStatus.RESOLVED
        ticket.resolved_at = now

    def escalate_overdue(self, now: datetime) -> list[SupportTicket]:
        """Move every overdue, unresolved/unescalated ticket to ESCALATED
        and return the ones just escalated."""
        escalated = []
        for ticket in self._tickets.values():
            if ticket.status in (TicketStatus.RESOLVED, TicketStatus.ESCALATED):
                continue
            if ticket.is_overdue(now):
                ticket.status = TicketStatus.ESCALATED
                escalated.append(ticket)
        return escalated

    def open_tickets(self) -> list[SupportTicket]:
        return [t for t in self._tickets.values() if t.status != TicketStatus.RESOLVED]

    def _require(self, ticket_id: str) -> SupportTicket:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            raise KeyError(f"Unknown ticket '{ticket_id}'")
        return ticket
