"""Writes the report files.

Sections: project status, weekly numbers, priority matrix, blocked tickets, warnings,
tickets. The AI summary (SRG-23) and the final layout (SRG-27, SRG-28) come later.
Each status is written as a word, never as a colour only (accessibility).
"""

from __future__ import annotations

import html
from pathlib import Path

from status_report.metrics import WeekMetrics
from status_report.models import Ticket
from status_report.project import LEVELS, ProjectStatus
from status_report.status import TICKET_STATUSES

COLUMNS = ("Key", "Title", "Type", "Status", "Jira status", "Priority", "Due")
NUMBER_LABELS = {
    "closed": "Closed this week",
    "opened": "Opened this week",
    "open": "Open at the end of the week",
    "blocked": "Blocked",
    "overdue": "Overdue",
}
SECTIONS = ("Project status", "Weekly numbers", "Priority matrix", "Tickets")


def _ticket_rows(tickets: list[Ticket], status: ProjectStatus) -> list[tuple[str, ...]]:
    return [
        (
            t.key,
            t.title,
            t.work_type,
            status.ticket_status.get(t.key, "Done" if t.is_done else "-"),
            t.status,
            t.priority or "-",
            t.due_date.isoformat() if t.due_date else "-",
        )
        for t in tickets
    ]


def _matrix_rows(status: ProjectStatus) -> list[tuple[str, ...]]:
    counts = status.counts()
    return [(s, *(str(counts[s][lv]) for lv in LEVELS)) for s in TICKET_STATUSES]


def _blocked_rows(metrics: WeekMetrics) -> list[tuple[str, str]]:
    return [(key, "n/a" if days is None else str(days)) for key, days in metrics.days_blocked.items()]


def _number_rows(metrics: WeekMetrics) -> list[tuple[str, str]]:
    return [(NUMBER_LABELS[name], str(value)) for name, value in metrics.counts().items()]


# --- Markdown -------------------------------------------------------------------

def _md_table(columns, rows) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append("| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |")
    return lines


def to_markdown(
    tickets: list[Ticket], metrics: WeekMetrics, status: ProjectStatus, project: str
) -> str:
    lines = [
        f"# Weekly Status Report: {project}",
        "",
        f"Week: {metrics.start} to {metrics.end}",
        "",
        "## Project status",
        "",
        f"**{status.status.upper()}** – {status.reason}",
        "",
        "## Weekly numbers",
        "",
        *_md_table(("Number", "Value"), _number_rows(metrics)),
        "",
        "## Priority matrix",
        "",
        *_md_table(("Status", *LEVELS), _matrix_rows(status)),
    ]
    if metrics.days_blocked:
        lines += ["", "## Blocked tickets", "", *_md_table(("Key", "Days blocked"), _blocked_rows(metrics))]
    if status.warnings:
        lines += ["", "## Warnings", "", *(f"- {w}" for w in status.warnings)]
    lines += ["", "## Tickets", "", *_md_table(COLUMNS, _ticket_rows(tickets, status))]
    return "\n".join(lines) + "\n"


# --- HTML -----------------------------------------------------------------------

def _html_table(columns, rows) -> str:
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def to_html(
    tickets: list[Ticket], metrics: WeekMetrics, status: ProjectStatus, project: str
) -> str:
    title = html.escape(f"Weekly Status Report: {project}")
    parts = [
        "<!doctype html>\n<html><head><meta charset='utf-8'>",
        f"<title>{title}</title></head><body>",
        f"<h1>{title}</h1><p>Week: {metrics.start} to {metrics.end}</p>",
        "<h2>Project status</h2>",
        f"<p><strong>{html.escape(status.status.upper())}</strong> – {html.escape(status.reason)}</p>",
        "<h2>Weekly numbers</h2>",
        _html_table(("Number", "Value"), _number_rows(metrics)),
        "<h2>Priority matrix</h2>",
        _html_table(("Status", *LEVELS), _matrix_rows(status)),
    ]
    if metrics.days_blocked:
        parts += ["<h2>Blocked tickets</h2>", _html_table(("Key", "Days blocked"), _blocked_rows(metrics))]
    if status.warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in status.warnings)
        parts += ["<h2>Warnings</h2>", f"<ul>{items}</ul>"]
    parts += ["<h2>Tickets</h2>", _html_table(COLUMNS, _ticket_rows(tickets, status)), "</body></html>\n"]
    return "".join(parts)


def write_report(
    tickets: list[Ticket],
    metrics: WeekMetrics,
    status: ProjectStatus,
    project: str,
    folder: Path,
    formats: tuple[str, ...],
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / f"status-report-{project}-{metrics.start}"
    paths = []
    if "markdown" in formats:
        path = base.with_suffix(".md")
        path.write_text(to_markdown(tickets, metrics, status, project), encoding="utf-8")
        paths.append(path)
    if "html" in formats:
        path = base.with_suffix(".html")
        path.write_text(to_html(tickets, metrics, status, project), encoding="utf-8")
        paths.append(path)
    return paths
