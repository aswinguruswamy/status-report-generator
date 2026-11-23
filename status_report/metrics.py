"""Spec §4 definitions (SRG v2). Each rule uses these words with these meanings only.

Times are aware datetimes. "Today" and the window use the timezone setting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from status_report.config import Config
from status_report.models import Ticket

DONE = "Done"
WINDOW_DAYS = 14
CLEANED_UP = {"won't do", "duplicate"}
NO_SPRINT_LABEL = "last 14 days"


def local_today(now: datetime, timezone: str) -> date:
    """Spec §4: today, local time (the timezone setting)."""
    return now.astimezone(ZoneInfo(timezone)).date()


def window_start(now: datetime, timezone: str) -> datetime:
    """Spec §4: the window starts at 00:00 on (today - 13 days), local time."""
    zone = ZoneInfo(timezone)
    first_day = now.astimezone(zone).date() - timedelta(days=WINDOW_DAYS - 1)
    return datetime.combine(first_day, time.min, zone)


def is_counted(ticket: Ticket, config: Config) -> bool:
    """Spec §4: a counted ticket has a type in work_types (no sub-tasks, no epics)."""
    return ticket.work_type in config.work_types


def is_cleaned_up(ticket: Ticket) -> bool:
    """Spec §4: resolved as Won't Do or Duplicate. Never done, open or in a total (R8.1)."""
    name = (ticket.resolution or "").replace("’", "'").strip().lower()
    return name in CLEANED_UP


def is_done(ticket: Ticket) -> bool:
    """Spec §4: in the Done status category and not cleaned up."""
    return ticket.status_category == DONE and not is_cleaned_up(ticket)


def is_open(ticket: Ticket) -> bool:
    """Spec §4: not in the Done status category. A reopened ticket is open."""
    return ticket.status_category != DONE and not is_cleaned_up(ticket)


def closed_at(ticket: Ticket) -> datetime | None:
    """Time of the last move into Done (v1 D19), for a done ticket. None if not done."""
    if not is_done(ticket):
        return None
    moves = [c.at for c in ticket.history if c.to_category == DONE]
    if moves:
        return max(moves)
    return ticket.done_date or ticket.resolved


def closed_in_window(ticket: Ticket, start: datetime, now: datetime) -> bool:
    """Spec §4: done, and the last move into Done is inside the window. Counts once."""
    moment = closed_at(ticket)
    return moment is not None and start <= moment <= now


def opened_in_window(ticket: Ticket, start: datetime, now: datetime) -> bool:
    """Spec §4: created inside the window, not cleaned up."""
    return start <= ticket.created <= now and not is_cleaned_up(ticket)


def moved_in_window(ticket: Ticket, start: datetime, now: datetime) -> bool:
    """The ticket moved to another status inside the window."""
    return any(start <= change.at <= now for change in ticket.history)


def sprint_end_date(ticket: Ticket, timezone: str) -> date | None:
    """End date (local) of the ticket's sprint: its active sprint, else its latest sprint."""
    dated = [s for s in ticket.sprints if s.end is not None]
    if not dated:
        return None
    active = [s for s in dated if s.state == "active"]
    sprint = max(active or dated, key=lambda s: s.end)
    return sprint.end.astimezone(ZoneInfo(timezone)).date()


def effective_due_date(ticket: Ticket, timezone: str) -> date | None:
    """Spec §4: the due date; if none, the end date of its sprint; if none, no date."""
    return ticket.due_date or sprint_end_date(ticket, timezone)


def is_overdue(ticket: Ticket, today: date, timezone: str) -> bool:
    """Spec §4: open, and the effective due date is before today."""
    due = effective_due_date(ticket, timezone)
    return is_open(ticket) and due is not None and due < today


def is_blocked(ticket: Ticket, config: Config) -> bool:
    """Spec §4: open, and found by the blocked_method setting (status, flag or label), now."""
    if not is_open(ticket):
        return False
    by_status = (
        "status" in config.blocked_methods
        and config.blocked_status_name is not None
        and ticket.status.lower() == config.blocked_status_name.lower()
    )
    by_flag = "flag" in config.blocked_methods and ticket.flagged
    by_label = (
        "label" in config.blocked_methods
        and config.blocked_label is not None
        and config.blocked_label.lower() in (label.lower() for label in ticket.labels)
    )
    return by_status or by_flag or by_label


def is_not_started(ticket: Ticket) -> bool:
    """Spec §4: status category To Do."""
    return ticket.status_category == "To Do"


def in_active_sprint(ticket: Ticket, active_ids: set[int]) -> bool:
    return any(s.id in active_ids for s in ticket.sprints)


@dataclass(frozen=True)
class ColourScope:
    """Spec §4: the tickets the team colour and done/total use."""

    tickets: tuple[Ticket, ...]  # Counted, not cleaned up
    sprints: int  # Number of active sprints; 0 = no-sprint scope ("last 14 days")

    @property
    def done(self) -> int:
        return sum(1 for t in self.tickets if is_done(t))

    @property
    def total(self) -> int:
        return len(self.tickets)

    @property
    def open(self) -> tuple[Ticket, ...]:
        return tuple(t for t in self.tickets if is_open(t))


def colour_scope(
    tickets, active_sprint_ids, config: Config, now: datetime
) -> ColourScope:
    """Spec §4: sprint scope; for a team with no active sprint, no-sprint scope.

    Sprint scope: counted tickets in the active sprint(s) now. A ticket moved out of the
    sprint is not in scope. No-sprint scope: counted tickets created, moved to another
    status, or closed inside the window. Cleaned-up tickets are never in scope (R8.1).
    """
    counted = [t for t in tickets if is_counted(t, config) and not is_cleaned_up(t)]
    ids = set(active_sprint_ids)
    if ids:
        return ColourScope(tuple(t for t in counted if in_active_sprint(t, ids)), len(ids))
    start = window_start(now, config.timezone)
    scope = tuple(
        t for t in counted
        if opened_in_window(t, start, now)
        or moved_in_window(t, start, now)
        or closed_in_window(t, start, now)
    )
    return ColourScope(scope, 0)


def window_counts(tickets, config: Config, now: datetime) -> tuple[int, int]:
    """(closed, opened) in the window for the whole project (spec R7.1, R11.2)."""
    start = window_start(now, config.timezone)
    counted = [t for t in tickets if is_counted(t, config)]
    closed = sum(1 for t in counted if closed_in_window(t, start, now))
    opened = sum(1 for t in counted if opened_in_window(t, start, now))
    return closed, opened
