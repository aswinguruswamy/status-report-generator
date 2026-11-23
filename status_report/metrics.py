"""Weekly numbers (SRG-19, D19, D23).

Each number shows the state at the end of the week, from the status history.
A report made later for an earlier week shows that week, not today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from status_report.config import Config
from status_report.models import Ticket

DONE = "Done"


@dataclass(frozen=True)
class WeekMetrics:
    start: date
    end: date
    closed: tuple[str, ...]
    opened: tuple[str, ...]
    open: tuple[str, ...]
    blocked: tuple[str, ...]
    overdue: tuple[str, ...]
    days_blocked: dict[str, int | None] = field(default_factory=dict)
    as_of: datetime | None = None  # The moment the numbers describe
    today: date | None = None  # First day that is not yet past (for overdue and amber)

    def counts(self) -> dict[str, int]:
        return {
            "closed": len(self.closed),
            "opened": len(self.opened),
            "open": len(self.open),
            "blocked": len(self.blocked),
            "overdue": len(self.overdue),
        }


def week_limits(start: date, end: date, timezone: str) -> tuple[datetime, datetime]:
    """Return the start of Monday and the start of the day after Sunday, in local time."""
    zone = ZoneInfo(timezone)
    return (
        datetime.combine(start, time.min, zone),
        datetime.combine(end + timedelta(days=1), time.min, zone),
    )


def category_at(ticket: Ticket, moment: datetime) -> str | None:
    """Status category of the ticket at the moment, or None if it did not exist yet."""
    if ticket.created >= moment:
        return None
    before = [c for c in ticket.history if c.at < moment]
    if before:
        return before[-1].to_category
    if ticket.history:
        return ticket.history[0].from_category
    if ticket.is_done and ticket.done_date and ticket.done_date >= moment:
        return "To Do"  # No history: closed after the moment (Resolved date, D19)
    return ticket.status_category


def status_at(ticket: Ticket, moment: datetime) -> str:
    before = [c for c in ticket.history if c.at < moment]
    if before:
        return before[-1].to_status
    if ticket.history:
        return ticket.history[0].from_status or ticket.status
    return ticket.status


def last_done_move(ticket: Ticket, moment: datetime) -> datetime | None:
    """Time of the last move into a Done status before the moment (D19)."""
    moves = [c.at for c in ticket.history if c.at < moment and c.to_category == DONE]
    if moves:
        return moves[-1]
    if not ticket.history and ticket.done_date and ticket.done_date < moment:
        return ticket.done_date  # Resolved date as the second check
    return None


def is_blocked(ticket: Ticket, config: Config, moment: datetime) -> bool:
    methods = config.blocked_methods
    by_status = (
        "status" in methods
        and config.blocked_status_name is not None
        and status_at(ticket, moment).lower() == config.blocked_status_name.lower()
    )
    by_flag = "flag" in methods and ticket.flagged
    by_label = (
        "label" in methods
        and config.blocked_label is not None
        and config.blocked_label.lower() in (label.lower() for label in ticket.labels)
    )
    return by_status or by_flag or by_label


def days_blocked(ticket: Ticket, config: Config, moment: datetime) -> int | None:
    """Days since the ticket entered the blocked status. None if the history cannot tell."""
    if "status" not in config.blocked_methods or not config.blocked_status_name:
        return None
    name = config.blocked_status_name.lower()
    if status_at(ticket, moment).lower() != name:
        return None
    entries = [c.at for c in ticket.history if c.at < moment and c.to_status.lower() == name]
    since = entries[-1] if entries else ticket.created
    return max(0, (moment - since).days)


def tickets_in_week(tickets: list[Ticket], metrics: WeekMetrics) -> list[Ticket]:
    """The tickets that the report shows: opened, closed, or open in the week."""
    keys = set(metrics.opened) | set(metrics.closed) | set(metrics.open)
    return [t for t in tickets if t.key in keys]


def calculate(
    tickets: list[Ticket], config: Config, start: date, end: date, now: datetime | None = None
) -> WeekMetrics:
    week_start, week_end = week_limits(start, end, config.timezone)
    moment = min(week_end, now) if now else week_end
    # Overdue: the due date has passed. For a finished week, a ticket due on Sunday
    # and still open is overdue. For the current week, compare with today.
    zone = ZoneInfo(config.timezone)
    last_day = end + timedelta(days=1) if moment == week_end else moment.astimezone(zone).date()
    counted = [t for t in tickets if t.work_type in config.work_types]  # D23

    closed, opened, open_, blocked, overdue = [], [], [], [], []
    blocked_days: dict[str, int | None] = {}
    for ticket in counted:
        if week_start <= ticket.created < week_end:
            opened.append(ticket.key)

        category = category_at(ticket, moment)
        if category is None:
            continue
        if category == DONE:
            done_at = last_done_move(ticket, moment)
            if done_at and done_at >= week_start:
                closed.append(ticket.key)
            continue

        open_.append(ticket.key)
        if is_blocked(ticket, config, moment):
            blocked.append(ticket.key)
            blocked_days[ticket.key] = days_blocked(ticket, config, moment)
        if ticket.due_date and ticket.due_date < last_day:
            overdue.append(ticket.key)

    return WeekMetrics(
        start=start,
        end=end,
        closed=tuple(closed),
        opened=tuple(opened),
        open=tuple(open_),
        blocked=tuple(blocked),
        overdue=tuple(overdue),
        days_blocked=blocked_days,
        as_of=moment,
        today=last_day,
    )


# =====================================================================================
# v2 definitions (spec §4, SRG-R8.1; plan S4). Each rule uses these words only.
# The v1 weekly functions above stay until the v1 weekly report is removed (plan S8).
# =====================================================================================

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


def is_done_v2(ticket: Ticket) -> bool:
    """Spec §4: in the Done status category and not cleaned up."""
    return ticket.status_category == DONE and not is_cleaned_up(ticket)


def is_open_v2(ticket: Ticket) -> bool:
    """Spec §4: not in the Done status category. A reopened ticket is open."""
    return ticket.status_category != DONE and not is_cleaned_up(ticket)


def closed_at(ticket: Ticket) -> datetime | None:
    """Time of the last move into Done (v1 D19), for a done ticket. None if not done."""
    if not is_done_v2(ticket):
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


def is_overdue_v2(ticket: Ticket, today: date, timezone: str) -> bool:
    """Spec §4: open, and the effective due date is before today."""
    due = effective_due_date(ticket, timezone)
    return is_open_v2(ticket) and due is not None and due < today


def is_blocked_v2(ticket: Ticket, config: Config) -> bool:
    """Spec §4: open, and found by the blocked_method setting (status, flag or label), now."""
    if not is_open_v2(ticket):
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
        return sum(1 for t in self.tickets if is_done_v2(t))

    @property
    def total(self) -> int:
        return len(self.tickets)

    @property
    def open(self) -> tuple[Ticket, ...]:
        return tuple(t for t in self.tickets if is_open_v2(t))


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
