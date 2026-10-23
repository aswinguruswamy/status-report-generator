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
