from datetime import UTC, datetime, timedelta

from app.mission_planning.customer_support import (
    SupportQueue,
    SupportTicket,
    TicketPriority,
    TicketStatus,
)


def _ticket(priority, opened_at, ticket_id="t1"):
    return SupportTicket(
        id=ticket_id, customer_id=1, subject="Help", priority=priority, opened_at=opened_at
    )


def test_ticket_is_not_overdue_before_its_sla():
    now = datetime.now(UTC)
    ticket = _ticket(TicketPriority.NORMAL, opened_at=now)
    assert ticket.is_overdue(now + timedelta(hours=1)) is False


def test_ticket_is_overdue_after_its_sla():
    now = datetime.now(UTC)
    ticket = _ticket(TicketPriority.URGENT, opened_at=now)  # 2h SLA
    assert ticket.is_overdue(now + timedelta(hours=3)) is True


def test_resolved_ticket_is_never_overdue():
    now = datetime.now(UTC)
    ticket = _ticket(TicketPriority.URGENT, opened_at=now)
    ticket.status = TicketStatus.RESOLVED
    assert ticket.is_overdue(now + timedelta(days=1)) is False


def test_escalate_overdue_moves_status_and_returns_only_newly_escalated():
    now = datetime.now(UTC)
    queue = SupportQueue()
    queue.open_ticket(_ticket(TicketPriority.URGENT, opened_at=now - timedelta(hours=5), ticket_id="overdue"))
    queue.open_ticket(_ticket(TicketPriority.LOW, opened_at=now, ticket_id="fine"))

    escalated = queue.escalate_overdue(now)

    assert [t.id for t in escalated] == ["overdue"]
    assert queue.get("overdue").status == TicketStatus.ESCALATED
    assert queue.get("fine").status == TicketStatus.OPEN

    # Running it again shouldn't re-escalate the same ticket.
    assert queue.escalate_overdue(now) == []


def test_resolve_removes_ticket_from_open_tickets():
    now = datetime.now(UTC)
    queue = SupportQueue()
    queue.open_ticket(_ticket(TicketPriority.NORMAL, opened_at=now))

    queue.resolve("t1", now)

    assert queue.open_tickets() == []
    assert queue.get("t1").status == TicketStatus.RESOLVED


def test_resolving_unknown_ticket_raises():
    import pytest

    queue = SupportQueue()
    with pytest.raises(KeyError):
        queue.resolve("nope", datetime.now(UTC))
