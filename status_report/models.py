"""The common objects: Ticket, Sprint, Release and TeamData (SRG-13; v2 plan S3).

The tool keeps only these fields. It does not keep descriptions or comments (D03).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class StatusChange:
    at: datetime
    from_status: str | None
    to_status: str
    from_category: str | None = None  # "To Do", "In Progress", or "Done"
    to_category: str | None = None


@dataclass(frozen=True)
class Sprint:
    id: int
    name: str
    state: str  # "active", "closed" or "future"
    end: datetime | None = None


@dataclass(frozen=True)
class Release:
    """A Jira fix version with a release date."""

    name: str
    release_date: date


@dataclass(frozen=True)
class Ticket:
    key: str
    title: str
    work_type: str
    status: str
    status_category: str  # "To Do", "In Progress", or "Done"
    priority: str | None
    assignee: str | None  # Shown in the report
    due_date: date | None
    created: datetime
    done_date: datetime | None  # Date of the last move into a Done status (D19)
    resolved: datetime | None  # Second check only (D19)
    labels: tuple[str, ...] = ()
    flagged: bool = False
    history: tuple[StatusChange, ...] = field(default=())
    story_points: float | None = None  # Used by the simulated teams (D20)
    resolution: str | None = None  # For example Done, Won't Do, Duplicate
    sprints: tuple[Sprint, ...] = ()  # All sprints of the ticket, from the Sprint field

    @property
    def is_done(self) -> bool:
        return self.status_category == "Done"


@dataclass(frozen=True)
class TeamData:
    """Everything SRG reads from Jira for one team (one project) at one time."""

    key: str
    tickets: tuple[Ticket, ...]  # Counted work types: all open tickets, and the recent others
    active_sprints: tuple[Sprint, ...]  # Active sprints on the project's boards
    next_release: Release | None  # Unreleased fix version, earliest release date >= today
    first_closed: datetime | None  # First closed ticket (not cleaned up); None if none or not read
    read_at: datetime
    browse_url: str | None = None  # For example https://site/browse/ ; None for sample data
