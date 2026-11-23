"""The team table: one row for each team, with colour, reason and done/total
(spec SRG-R1, SRG-R2, SRG-R3.2, SRG-R9, SRG-R11, N4.1; plan S6).

Code makes every number, colour and text here (spec P1). The page and the report only
show a Portfolio; they make no rule decisions of their own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from status_report.config import PRIORITY_LEVELS, UNMAPPED, Config, Team
from status_report.forecast import Forecast, team_forecast
from status_report.metrics import NO_SPRINT_LABEL, colour_scope, local_today, window_counts
from status_report.models import TeamData
from status_report.project import key_order, team_status
from status_report.status import AMBER, BLACK, GREEN, RED

COLOUR_ORDER = {RED: 0, AMBER: 1, GREEN: 2}  # Spec R1.2
PROBLEM_ORDER = {BLACK: 0, RED: 1, AMBER: 2}  # Spec R11.1
LEVEL_ORDER = {level: n for n, level in enumerate((*PRIORITY_LEVELS, UNMAPPED))}
COULD_NOT_READ = "Could not read"


@dataclass(frozen=True)
class ProblemTicket:
    """A Black, Red or Amber ticket in the team details (spec R11.1)."""

    key: str
    title: str
    priority: str  # Jira priority name, or "-"
    level: str  # P1 to P5, or Unmapped
    colour: str
    cause: str
    url: str | None  # Jira link; None for sample data (R11.3)


@dataclass(frozen=True)
class TeamRow:
    key: str
    name: str
    colour: str | None  # Red, Amber or Green; None when the team could not be read
    reason: str
    done: int = 0
    total: int = 0
    sprints: int = 0  # 0 = no active sprint: "last 14 days"
    no_due_percent: int | None = None  # None when there are no open tickets (R9.1)
    closed: int = 0
    opened: int = 0
    problems: tuple[ProblemTicket, ...] = ()
    warnings: tuple[str, ...] = ()
    error: str | None = None
    forecast: Forecast | None = None  # None when the forecast setting is off (R4)

    @property
    def progress(self) -> str:
        """Done/total, for example "3/5", "4/9 · 2 sprints" or "1/4 · last 14 days"."""
        if self.error:
            return "–"
        text = f"{self.done}/{self.total}"
        if self.sprints == 0:
            return f"{text} · {NO_SPRINT_LABEL}"
        if self.sprints > 1:
            return f"{text} · {self.sprints} sprints"
        return text

    @property
    def no_due_text(self) -> str | None:
        if self.no_due_percent is None:
            return None
        return f"{self.no_due_percent}% of open tickets have no due date"

    @property
    def window_text(self) -> str:
        return f"Closed {self.closed} · Opened {self.opened} in the last 14 days"


@dataclass(frozen=True)
class Portfolio:
    rows: tuple[TeamRow, ...]
    read_at: datetime
    timezone: str
    sample: bool = False  # Demo mode: "Sample data" (R14.2)
    warnings: tuple[str, ...] = field(default=())

    @property
    def as_of(self) -> str:
        """Spec R3.2: "as of hh:mm", local time."""
        return f"as of {self.read_at.astimezone(ZoneInfo(self.timezone)):%H:%M}"

    @property
    def read_date(self) -> str:
        return f"{self.read_at.astimezone(ZoneInfo(self.timezone)):%Y-%m-%d}"


def percent(part: int, whole: int) -> int:
    """Rounded to the nearest whole number; a half goes up (spec R9.1)."""
    return (200 * part + whole) // (2 * whole)


def build_row(team: Team, data: TeamData | Exception, config: Config, now: datetime) -> TeamRow:
    """One table row. A team that could not be read gets an error row (spec N4.1)."""
    if isinstance(data, Exception):
        message = str(data) or type(data).__name__
        return TeamRow(team.key, team.name, None, f"{COULD_NOT_READ} – {message}", error=message)
    today = local_today(now, config.timezone)
    scope = colour_scope(data.tickets, [s.id for s in data.active_sprints], config, now)
    closed, opened = window_counts(data.tickets, config, now)
    status = team_status(scope.tickets, closed, opened, config, today)
    open_tickets = scope.open
    no_due = sum(1 for t in open_tickets if t.due_date is None)
    by_key = {t.key: t for t in scope.tickets}
    problems = [
        ProblemTicket(
            key=key,
            title=by_key[key].title,
            priority=by_key[key].priority or "-",
            level=config.priority_level(by_key[key].priority),
            colour=colour.colour,
            cause=colour.cause[0].upper() + colour.cause[1:],
            url=f"{data.browse_url}{key}" if data.browse_url else None,
        )
        for key, colour in status.ticket_colours.items()
        if colour.colour in PROBLEM_ORDER
    ]
    problems.sort(key=lambda p: (PROBLEM_ORDER[p.colour], LEVEL_ORDER[p.level], key_order(p.key)))
    return TeamRow(
        key=team.key,
        name=team.name,
        colour=status.colour,
        reason=status.reason,
        done=scope.done,
        total=scope.total,
        sprints=scope.sprints,
        no_due_percent=percent(no_due, len(open_tickets)) if open_tickets else None,
        closed=closed,
        opened=opened,
        problems=tuple(problems),
        warnings=status.warnings,
        forecast=team_forecast(data, config, now) if config.forecast else None,
    )


def row_order(row: TeamRow) -> tuple:
    """Rows that could not be read first (so a failure is seen), then Red, Amber, Green,
    then team name A–Z (spec R1.2)."""
    colour = -1 if row.colour is None else COLOUR_ORDER[row.colour]
    return (colour, row.name.casefold(), row.key)


def build_portfolio(
    config: Config, results: dict, read_at: datetime, sample: bool = False
) -> Portfolio:
    """The table for every team in the settings, from read_teams() results."""
    rows = [build_row(team, results[team.key], config, read_at) for team in config.teams]
    rows.sort(key=row_order)
    warnings = tuple(w for row in rows for w in row.warnings)
    return Portfolio(tuple(rows), read_at, config.timezone, sample, warnings)
