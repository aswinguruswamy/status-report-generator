"""Team colour and reason (spec SRG-R7.1, SRG-R10; the v1 priority rule).

The first true rule wins:
  Red   = 1 or more high-priority tickets (P1, P2) are Black or Red
  Amber = 1 or more other tickets are Black or Red, or 1 or more high-priority tickets
          are Amber, or closed in the window < opened in the window (whole project)
  Green = none of these. A team is never Black.
The reason parts follow the same order. Only these rules set the colour (spec SRG-R5.1);
there is no AI in SRG v2, and the forecast never changes the colour (R4.2).
"""

from __future__ import annotations

from dataclasses import dataclass

from status_report.config import PRIORITY_LEVELS, UNMAPPED, Config
from status_report.status import (
    AMBER,
    BLACK,
    BLOCKED,
    DUE_SOON,
    GREEN,
    NO_DUE_DATE,
    OVERDUE,
    RED,
    TicketColour,
    ticket_colour,
)

LEVELS = (*PRIORITY_LEVELS, UNMAPPED)
MAX_KEYS = 3  # Keys named in each part of the reason; the details list has all of them

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
