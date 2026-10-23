"""Ticket status: Black, Red, Amber, or Green (SRG-20, D21, D22).

The tool checks each open ticket in this order. The first true rule sets the status.
  1. Black: overdue (also when blocked)
  2. Red: blocked, not overdue
  3. Amber: due within amber_window_days and still in amber_status_category (D22)
  4. Green: all other open tickets
Done tickets get no status. A ticket with no due date can only be Red or Green.
"""

from __future__ import annotations

from status_report.config import Config
from status_report.metrics import WeekMetrics, category_at
from status_report.models import Ticket

BLACK = "Black"
RED = "Red"
AMBER = "Amber"
GREEN = "Green"
TICKET_STATUSES = (BLACK, RED, AMBER, GREEN)


def ticket_status(ticket: Ticket, metrics: WeekMetrics, config: Config) -> str | None:
    """Status of one ticket at the end of the week. None for a ticket that is not open."""
    if ticket.key not in metrics.open:
        return None
    if ticket.key in metrics.overdue:
        return BLACK
    if ticket.key in metrics.blocked:
        return RED
    if ticket.due_date is not None and metrics.today is not None and metrics.as_of is not None:
        days_left = (ticket.due_date - metrics.today).days
        not_started = category_at(ticket, metrics.as_of) == config.amber_status_category
        if 0 <= days_left <= config.amber_window_days and not_started:
            return AMBER
    return GREEN


def ticket_statuses(tickets: list[Ticket], metrics: WeekMetrics, config: Config) -> dict[str, str]:
    """Status for each open ticket, by ticket key."""
    result = {}
    for ticket in tickets:
        status = ticket_status(ticket, metrics, config)
        if status is not None:
            result[ticket.key] = status
    return result
