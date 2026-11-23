"""Priority matrix and project status (SRG-21, D21).

The project status is only Red, Amber, or Green. Black counts as Red here.
  Red:   one or more high-priority tickets (P1, P2) are Red or Black.
  Amber: one or more other tickets are Red or Black, or one or more high-priority
         tickets are Amber, or the team closed fewer tickets than it opened.
  Green: none of the above.
Only these rules set the status (v2 spec SRG-R5.1). There is no AI in SRG v2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from status_report.config import PRIORITY_LEVELS, UNMAPPED, Config
from status_report.metrics import WeekMetrics
from status_report.models import Ticket
from status_report.status import (
    AMBER,
    BLACK,
    BLOCKED,
    DUE_SOON,
    GREEN,
    NO_DUE_DATE,
    OVERDUE,
    RED,
    TICKET_STATUSES,
    TicketColour,
    ticket_colour,
    ticket_statuses,
)

LEVELS = (*PRIORITY_LEVELS, UNMAPPED)
WHY = {BLACK: "overdue", RED: "blocked", AMBER: "due soon and not started"}
MAX_KEYS = 3  # Keys named in each part of the reason; the report table has all (SRG-36, D43)


@dataclass(frozen=True)
class ProjectStatus:
    status: str  # Red, Amber, or Green
    reason: str  # One line for the executive, for example "Red: 1 P1 ticket is blocked (SRG-12)."
    matrix: dict[str, dict[str, list[str]]]  # ticket status -> priority level -> ticket keys
    ticket_status: dict[str, str]  # ticket key -> ticket status
    warnings: list[str] = field(default_factory=list)

    def counts(self) -> dict[str, dict[str, int]]:
        return {s: {lv: len(keys) for lv, keys in row.items()} for s, row in self.matrix.items()}


def build_matrix(
    tickets: list[Ticket], statuses: dict[str, str], config: Config
) -> dict[str, dict[str, list[str]]]:
    matrix = {status: {level: [] for level in LEVELS} for status in TICKET_STATUSES}
    for ticket in tickets:
        status = statuses.get(ticket.key)
        if status is not None:
            matrix[status][config.priority_level(ticket.priority)].append(ticket.key)
    return matrix


def _phrase(level: str, status: str, keys: list[str]) -> str:
    noun = "ticket is" if len(keys) == 1 else "tickets are"
    shown = ", ".join(keys[:MAX_KEYS])
    if len(keys) > MAX_KEYS:
        shown += f", and {len(keys) - MAX_KEYS} more"
    return f"{len(keys)} {level} {noun} {WHY[status]} ({shown})"


def _phrases(matrix, levels, statuses) -> list[str]:
    return [
        _phrase(level, status, matrix[status][level])
        for status in statuses
        for level in levels
        if matrix[status][level]
    ]


def project_status(
    tickets: list[Ticket], metrics: WeekMetrics, config: Config
) -> ProjectStatus:
    statuses = ticket_statuses(tickets, metrics, config)
    matrix = build_matrix(tickets, statuses, config)
    high = [lv for lv in LEVELS if lv in config.high_priorities]
    other = [lv for lv in LEVELS if lv not in config.high_priorities]  # Includes Unmapped

    warnings = [
        config.unmapped_warning(t.key, t.priority)
        for t in tickets
        if t.key in statuses and config.priority_level(t.priority) == UNMAPPED
    ]

    red = _phrases(matrix, high, (BLACK, RED))
    if red:
        status, reason = RED, "; ".join(red)
    else:
        amber = _phrases(matrix, other, (BLACK, RED)) + _phrases(matrix, high, (AMBER,))
        closed, opened = len(metrics.closed), len(metrics.opened)
        if closed < opened:
            amber.append(f"the team closed {closed} and opened {opened} tickets")
        if amber:
            status, reason = AMBER, "; ".join(amber)
        elif not statuses:
            status, reason = GREEN, "No open tickets"
        else:
            status, reason = GREEN, "No blocked, overdue, or at-risk tickets"

    text = reason[0].upper() + reason[1:]
    return ProjectStatus(
        status=status,
        reason=f"{status}: {text}.",
        matrix=matrix,
        ticket_status=statuses,
        warnings=warnings,
    )


# =====================================================================================
# v2 team colour and reason (spec SRG-R7.1, SRG-R10; plan S5). The first true rule wins:
#   Red   = 1 or more high-priority tickets are Black or Red
#   Amber = 1 or more other tickets are Black or Red, or 1 or more high-priority tickets
#           are Amber, or closed in the window < opened in the window (whole project)
#   Green = none of these. A team is never Black.
# The reason parts follow the same order. The forecast never changes the colour (R4.2).
# =====================================================================================

VERB = {  # cause -> (one ticket, more tickets)
    OVERDUE: ("ticket is overdue", "tickets are overdue"),
    BLOCKED: ("ticket is blocked", "tickets are blocked"),
    DUE_SOON: ("ticket is due soon and not started", "tickets are due soon and not started"),
    NO_DUE_DATE: ("ticket has no due date", "tickets have no due date"),
}
GREEN_OK = "Green: No blocked, overdue, or at-risk tickets."
GREEN_EMPTY = "Green: No open tickets."


@dataclass(frozen=True)
class TeamStatus:
    colour: str  # Red, Amber or Green
    reason: str  # For example "Red: 1 P1 ticket is blocked (BET-12)."
    ticket_colours: dict[str, TicketColour]  # Open scope tickets, by key
    warnings: tuple[str, ...] = ()


def key_order(key: str) -> tuple[str, int, str]:
    """ALP-9 before ALP-10."""
    prefix, _, number = key.rpartition("-")
    return (prefix, int(number), key) if number.isdigit() else (key, 0, key)


def _part(level: str, cause: str, keys: list[str]) -> str:
    keys = sorted(keys, key=key_order)
    verb = VERB[cause][0 if len(keys) == 1 else 1]
    shown = ", ".join(keys[:MAX_KEYS])
    if len(keys) > MAX_KEYS:
        shown += f", and {len(keys) - MAX_KEYS} more"
    return f"{len(keys)} {level} {verb} ({shown})"


def team_status(scope_tickets, closed: int, opened: int, config: Config, today) -> TeamStatus:
    """Team colour and reason from the open tickets in the colour scope (spec R7.1, R10)."""
    colours: dict[str, TicketColour] = {}
    level_of: dict[str, str] = {}
    warnings = []
    for ticket in scope_tickets:
        colour = ticket_colour(ticket, config, today)
        if colour is None:
            continue
        colours[ticket.key] = colour
        level_of[ticket.key] = config.priority_level(ticket.priority)
        if level_of[ticket.key] == UNMAPPED:
            warnings.append(config.unmapped_warning(ticket.key, ticket.priority))  # R13.4
    high = [lv for lv in LEVELS if lv in config.high_priorities]
    other = [lv for lv in LEVELS if lv not in config.high_priorities]  # Includes Unmapped

    def parts(levels, rules):
        found = []
        for colour, cause in rules:
            for level in levels:
                keys = [k for k, c in colours.items()
                        if c.colour == colour and c.cause == cause and level_of[k] == level]
                if keys:
                    found.append(_part(level, cause, keys))
        return found

    black_red = ((BLACK, OVERDUE), (RED, BLOCKED))
    red = parts(high, black_red)
    if red:
        return TeamStatus(RED, _reason(RED, red), colours, tuple(warnings))
    amber = parts(other, black_red) + parts(high, ((AMBER, DUE_SOON), (AMBER, NO_DUE_DATE)))
    if closed < opened:
        noun = "ticket" if opened == 1 else "tickets"
        amber.append(f"the team closed {closed} and opened {opened} {noun} in the last 14 days")
    if amber:
        return TeamStatus(AMBER, _reason(AMBER, amber), colours, tuple(warnings))
    reason = GREEN_OK if colours else GREEN_EMPTY
    return TeamStatus(GREEN, reason, colours, tuple(warnings))


def _reason(colour: str, parts: list[str]) -> str:
    text = "; ".join(parts)
    return f"{colour}: {text[0].upper()}{text[1:]}."
