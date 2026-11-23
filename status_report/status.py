"""Ticket colour: Black, Red, Amber or Green (spec SRG-R6.1, SRG-R9; v1 rule order).

The first true rule wins:
  Black = overdue (effective due date before today; also when blocked)
  Red   = blocked
  Amber = (effective due date within amber_window_days and not started)
          or (no effective due date and high priority)
  Green = all other open tickets
A ticket that is not open (done or cleaned up) has no colour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from status_report.config import Config
from status_report.metrics import effective_due_date, is_blocked, is_not_started, is_open
from status_report.models import Ticket

BLACK = "Black"
RED = "Red"
AMBER = "Amber"
GREEN = "Green"
TICKET_STATUSES = (BLACK, RED, AMBER, GREEN)

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
    if not is_open(ticket):
        return None
    due = effective_due_date(ticket, config.timezone)
    if due is not None and due < today:
        return TicketColour(BLACK, OVERDUE)
    if is_blocked(ticket, config):
        return TicketColour(RED, BLOCKED)
    if due is not None and 0 <= (due - today).days <= config.amber_window_days and is_not_started(ticket):
        return TicketColour(AMBER, DUE_SOON)
    if due is None and config.is_high(ticket.priority):
        return TicketColour(AMBER, NO_DUE_DATE)
    return TicketColour(GREEN, None)
