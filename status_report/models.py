"""The common Ticket object (SRG-13).

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
class Ticket:
    key: str
    title: str
    work_type: str
    status: str
    status_category: str  # "To Do", "In Progress", or "Done"
    priority: str | None
    assignee: str | None  # Shown in the report. Never sent to the AI (D28).
    due_date: date | None
    created: datetime
    done_date: datetime | None  # Date of the last move into a Done status (D19)
    resolved: datetime | None  # Second check only (D19)
    labels: tuple[str, ...] = ()
    flagged: bool = False
    history: tuple[StatusChange, ...] = field(default=())
    story_points: float | None = None  # Used by the simulated teams (D20)

    @property
    def is_done(self) -> bool:
        return self.status_category == "Done"
