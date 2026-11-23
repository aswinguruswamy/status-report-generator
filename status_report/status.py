"""Ticket status: Black, Red, Amber, or Green (SRG-20, D21, D22).

The tool checks each open ticket in this order. The first true rule sets the status.
  1. Black: overdue (also when blocked)
  2. Red: blocked, not overdue
  3. Amber: due within amber_window_days and still in amber_status_category (D22)
  4. Green: all other open tickets
Done tickets get no status. A ticket with no due date can only be Red or Green.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from status_report.config import Config
from status_report.metrics import (
    WeekMetrics,
    category_at,
    effective_due_date,
    is_blocked_v2,
    is_not_started,
    is_open_v2,
)
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


# =====================================================================================
# v2 ticket colour (spec SRG-R6.1, SRG-R9; plan S5). The first true rule wins:
#   Black = overdue (effective due date before today)
#   Red   = blocked
#   Amber = (effective due date within amber_window_days and not started)
#           or (no effective due date and high priority)
#   Green = all other open tickets
# =====================================================================================

OVERDUE = "overdue"
BLOCKED = "blocked"
DUE_SOON = "due soon and not started"
NO_DUE_DATE = "high priority with no due date"


@dataclass(frozen=True)
class TicketColour:
    colour: str  # Black, Red, Amber or Green
    cause: str | None  # OVERDUE, BLOCKED, DUE_SOON, NO_DUE_DATE; None for Green


def ticket_colour(ticket: Ticket, config: Config, today: date) -> TicketColour | None:
    """Colour of one open ticket (spec SRG-R6.1). None for a ticket that is not open."""
    if not is_open_v2(ticket):
        return None
    due = effective_due_date(ticket, config.timezone)
    if due is not None and due < today:
        return TicketColour(BLACK, OVERDUE)
    if is_blocked_v2(ticket, config):
        return TicketColour(RED, BLOCKED)
    if due is not None and 0 <= (due - today).days <= config.amber_window_days and is_not_started(ticket):
        return TicketColour(AMBER, DUE_SOON)
    if due is None and config.is_high(ticket.priority):
        return TicketColour(AMBER, NO_DUE_DATE)
    return TicketColour(GREEN, None)
