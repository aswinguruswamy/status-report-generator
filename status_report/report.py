"""Writes the report files.

This version writes the weekly numbers and a ticket list (SRG-18, SRG-19).
The status rules, the AI summary, and the final layout come in SRG-20 to SRG-28.
"""

from __future__ import annotations

import html
from pathlib import Path

from status_report.metrics import WeekMetrics
from status_report.models import Ticket

COLUMNS = ("Key", "Title", "Type", "Status", "Priority", "Due")
NUMBER_LABELS = {
    "closed": "Closed this week",
    "opened": "Opened this week",
    "open": "Open at the end of the week",
    "blocked": "Blocked",
    "overdue": "Overdue",
}


def _rows(tickets: list[Ticket]) -> list[tuple[str, ...]]:
    return [
        (
            t.key,
            t.title,
            t.work_type,
            t.status,
            t.priority or "-",
            t.due_date.isoformat() if t.due_date else "-",
        )
        for t in tickets
    ]


def _blocked_rows(metrics: WeekMetrics) -> list[tuple[str, str]]:
    return [
        (key, "n/a" if days is None else str(days))
        for key, days in metrics.days_blocked.items()
    ]


def to_markdown(tickets: list[Ticket], metrics: WeekMetrics, project: str) -> str:
    counts = metrics.counts()
    lines = [
        f"# Weekly Status Report: {project}",
        "",
        f"Week: {metrics.start} to {metrics.end}",
        "",
        "## Weekly numbers",
        "",
        "| Number | Value |",
        "|---|---|",
        *(f"| {NUMBER_LABELS[name]} | {value} |" for name, value in counts.items()),
    ]
    if metrics.days_blocked:
        lines += ["", "## Blocked tickets", "", "| Key | Days blocked |", "|---|---|"]
        lines += [f"| {key} | {days} |" for key, days in _blocked_rows(metrics)]
    lines += [
        "",
        "## Tickets",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    for row in _rows(tickets):
        cells = [cell.replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _html_table(columns, rows) -> str:
    head = "".join(f"<th>{html.escape(c)}</th>" for c in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def to_html(tickets: list[Ticket], metrics: WeekMetrics, project: str) -> str:
    title = html.escape(f"Weekly Status Report: {project}")
    numbers = [(NUMBER_LABELS[name], value) for name, value in metrics.counts().items()]
    parts = [
        "<!doctype html>\n<html><head><meta charset='utf-8'>",
        f"<title>{title}</title></head><body>",
        f"<h1>{title}</h1><p>Week: {metrics.start} to {metrics.end}</p>",
        "<h2>Weekly numbers</h2>",
        _html_table(("Number", "Value"), numbers),
    ]
    if metrics.days_blocked:
        parts += ["<h2>Blocked tickets</h2>", _html_table(("Key", "Days blocked"), _blocked_rows(metrics))]
    parts += ["<h2>Tickets</h2>", _html_table(COLUMNS, _rows(tickets)), "</body></html>\n"]
    return "".join(parts)


def write_report(
    tickets: list[Ticket],
    metrics: WeekMetrics,
    project: str,
    folder: Path,
    formats: tuple[str, ...],
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / f"status-report-{project}-{metrics.start}"
    paths = []
    if "markdown" in formats:
        path = base.with_suffix(".md")
        path.write_text(to_markdown(tickets, metrics, project), encoding="utf-8")
        paths.append(path)
    if "html" in formats:
        path = base.with_suffix(".html")
        path.write_text(to_html(tickets, metrics, project), encoding="utf-8")
        paths.append(path)
    return paths
