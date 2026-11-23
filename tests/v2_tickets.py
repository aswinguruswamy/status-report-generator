"""Helpers for the v2 rule tests: a fixed read time and short ticket builders."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from status_report.config import Config, Team
from status_report.models import Sprint, StatusChange, Ticket

TZ = "America/Toronto"
ZONE = ZoneInfo(TZ)
TODAY = date(2026, 12, 1)
NOW = datetime(2026, 12, 1, 9, 42, tzinfo=ZONE)  # The read time
CONFIG = Config(teams=(Team("ALP", "Alpha"), Team("BET", "Beta")), timezone=TZ)
CATEGORY = {"To Do": "To Do", "In Progress": "In Progress", "Blocked": "In Progress",
            "In Review": "In Progress", "Done": "Done"}


def at(days: int, hour: int = 10) -> datetime:
    """A local time `days` from today (negative = before)."""
    return datetime.combine(TODAY + timedelta(days=days), time(hour), ZONE)


def sprint(sid: int = 7, end_days: int = 7, state: str = "active") -> Sprint:
    return Sprint(sid, f"Sprint {sid}", state, at(end_days, 17))


SPRINT = sprint()


def ticket(key: str = "BET-1", status: str = "To Do", priority: str | None = "Medium",
           due: int | None = None, created: int = -30, sprints=(SPRINT,), history=None,
           resolution: str | None = None, work_type: str = "Story", labels=(),
           flagged: bool = False, closed: int = -1) -> Ticket:
    """A ticket. due: days from today. A Done ticket closes `closed` days from today."""
    category = CATEGORY[status]
    if history is None:
        history = [StatusChange(at(closed), "In Progress", "Done", "In Progress", "Done")] \
            if category == "Done" else []
    if category == "Done" and resolution is None:
        resolution = "Done"
    done = [c.at for c in history if c.to_category == "Done"]
    return Ticket(
        key=key, title=f"Title {key}", work_type=work_type, status=status,
        status_category=category, priority=priority, assignee=None,
        due_date=TODAY + timedelta(days=due) if due is not None else None,
        created=at(created), done_date=done[-1] if category == "Done" and done else None,
        resolved=None, labels=tuple(labels), flagged=flagged, history=tuple(history),
        resolution=resolution, sprints=tuple(sprints),
    )


def move(days: int, old: str, new: str, hour: int = 10) -> StatusChange:
    return StatusChange(at(days, hour), old, new, CATEGORY[old], CATEGORY[new])
