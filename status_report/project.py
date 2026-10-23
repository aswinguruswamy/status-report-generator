"""Priority matrix and project status (SRG-21, D21).

The project status is only Red, Amber, or Green. Black counts as Red here.
  Red:   one or more high-priority tickets (P1, P2) are Red or Black.
  Amber: one or more other tickets are Red or Black, or one or more high-priority
         tickets are Amber, or the team closed fewer tickets than it opened.
  Green: none of the above.
The rules set the status. The AI never sets or changes it (D02).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from status_report.config import PRIORITY_LEVELS, UNMAPPED, Config
from status_report.metrics import WeekMetrics
from status_report.models import Ticket
from status_report.status import AMBER, BLACK, GREEN, RED, TICKET_STATUSES, ticket_statuses

LEVELS = (*PRIORITY_LEVELS, UNMAPPED)
WHY = {BLACK: "overdue", RED: "blocked", AMBER: "due soon and not started"}


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
    return f"{len(keys)} {level} {noun} {WHY[status]} ({', '.join(keys)})"


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
