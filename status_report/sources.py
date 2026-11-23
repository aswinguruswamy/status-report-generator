"""Data sources for tickets (D01).

The command uses only this interface. The Jira client is the v1 source.
A GitHub Issues source (v2) can implement the same two methods.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol

from status_report.models import Ticket


class TicketSource(Protocol):
    def connect(self) -> str:
        """Check the access. Return the name of the account."""
        ...

    def fetch_tickets(
        self,
        project_key: str,
        work_types: tuple[str, ...],
        start: date,
        end: date,
        need_flag: bool = False,
    ) -> list[Ticket]:
        """Return the tickets that can matter for the week. The tool filters them exactly."""
        ...


def default_source() -> TicketSource:
    """The v1 source: Jira, with the values from .env."""
    from status_report.jira_client import JiraClient

    return JiraClient.from_env()


# --- v2: read every team, 4 at a time (spec SRG-R3.1, N3, N4.1; plan SD3) ---------------

MAX_PARALLEL_READS = 4
HISTORY_DAYS = 84  # Forecast window (spec R4.1)
WINDOW_DAYS = 14  # Spec §4: the window


def read_teams(client, config, read_at, keys=None) -> dict:
    """Read each team in the settings in parallel.

    Returns {project key: TeamData or JiraError}. A failed team does not stop the others
    (spec N4.1). An error that stops every read (no connection, token not accepted) is
    raised by client.prepare() before the parallel reads start.
    """
    from concurrent.futures import ThreadPoolExecutor
    from zoneinfo import ZoneInfo

    from status_report.jira_client import JiraError

    keys = list(keys) if keys is not None else [team.key for team in config.teams]
    need_flag = "flag" in config.blocked_methods
    client.prepare(need_flag)
    today = read_at.astimezone(ZoneInfo(config.timezone)).date()
    lookback = HISTORY_DAYS if config.forecast else WINDOW_DAYS

    def read(key):
        try:
            return client.read_team(
                key, config.work_types, today, read_at, lookback,
                need_flag=need_flag, need_first_closed=config.forecast,
            )
        except JiraError as error:
            return error
        except Exception as error:  # noqa: BLE001 - one team must not stop the others (N4.1)
            return JiraError(f"Jira sent data that the tool cannot read ({type(error).__name__}).")

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_READS) as pool:
        return dict(zip(keys, pool.map(read, keys), strict=True))
