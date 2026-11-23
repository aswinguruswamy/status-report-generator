"""What the web page shows, without Streamlit (spec SRG-R3, R11, R14.2, N4.2, N9; plan S9).

app.py only draws what these functions return, so the page logic has unit tests.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from status_report.jira_client import JiraError
from status_report.portfolio import Portfolio, TeamRow
from status_report.report import marked

SAMPLE_BANNER = "Sample data – the teams and tickets are made up. No Jira account is used."
TABLE_COLUMNS = ("Team", "Colour", "Done/total", "Forecast", "Reason")
DETAIL_COLUMNS = ("Key", "Title", "Priority", "Colour", "Cause")


@dataclass(frozen=True)
class PageState:
    """The last good read, and the error of the last refresh if it failed (spec N4.2)."""

    last_good: Portfolio | None = None
    error: str | None = None
    failed_at: datetime | None = None


def whole_read_failed(portfolio: Portfolio) -> str | None:
    """A refresh fails as a whole when no team could be read. Returns the first reason."""
    if portfolio.rows and all(row.error for row in portfolio.rows):
        return portfolio.rows[0].error
    return None


def refresh(state: PageState, read: Callable[[], Portfolio], now: datetime) -> PageState:
    """Read Jira again (spec R3.1). If the whole read fails, keep the last good read and
    show the error; the old data is never shown as new (N4.2)."""
    try:
        portfolio = read()
    except JiraError as error:
        return PageState(state.last_good, str(error), now)
    failed = whole_read_failed(portfolio)
    if failed and state.last_good is not None:
        return PageState(state.last_good, failed, now)
    return PageState(portfolio)


def headline(state: PageState) -> str:
    """"As of 09:42", or the error with "Last good read 09:00" (spec R3.2, N4.2)."""
    good = state.last_good
    if state.error:
        last = f" Last good read {_hhmm(good)}." if good else " There is no good read yet."
        return f"Could not refresh: {state.error}{last}"
    return f"Team status {good.as_of}" if good else "No data yet."


def _hhmm(portfolio: Portfolio) -> str:
    return f"{portfolio.read_at.astimezone(ZoneInfo(portfolio.timezone)):%H:%M}"


def table_rows(portfolio: Portfolio) -> list[dict[str, str]]:
    """The team table: every colour as a mark and a word (N9)."""
    return [
        {
            "Team": row.name,
            "Colour": marked(row.colour),
            "Done/total": row.progress,
            "Forecast": row.forecast.text if row.forecast else "–",
            "Reason": row.reason,
        }
        for row in portfolio.rows
    ]


def detail_lines(row: TeamRow) -> list[str]:
    """Lines above the ticket list when a team row is clicked (R11.2, R9.1)."""
    if row.error:
        return [row.reason]
    return [row.reason] + [line for line in (row.no_due_text, row.window_text) if line]


def detail_rows(row: TeamRow) -> list[dict[str, str | None]]:
    """The team's Black, Red and Amber tickets, in the R11.1 order. "Link" only for real data."""
    return [
        {
            "Key": p.key,
            "Title": p.title,
            "Priority": p.priority,
            "Colour": marked(p.colour),
            "Cause": p.cause,
            "Link": p.url,
        }
        for p in row.problems
    ]
