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
