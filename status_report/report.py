"""Writes the report files.

This first version writes a ticket list only (SRG-18). The weekly numbers, the
status rules, the AI summary, and the final layout come in SRG-19 to SRG-28.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from status_report.models import Ticket

COLUMNS = ("Key", "Title", "Type", "Status", "Priority", "Due")


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


def to_markdown(tickets: list[Ticket], project: str, start: date, end: date) -> str:
    lines = [
        f"# Weekly Status Report: {project}",
        "",
        f"Week: {start} to {end}  ",
        f"Tickets: {len(tickets)}",
        "",
        "| " + " | ".join(COLUMNS) + " |",
        "|" + "---|" * len(COLUMNS),
    ]
    for row in _rows(tickets):
        cells = [cell.replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def to_html(tickets: list[Ticket], project: str, start: date, end: date) -> str:
    head = "".join(f"<th>{c}</th>" for c in COLUMNS)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in _rows(tickets)
    )
    title = html.escape(f"Weekly Status Report: {project}")
    return (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        f"<title>{title}</title></head><body>"
        f"<h1>{title}</h1><p>Week: {start} to {end}<br>Tickets: {len(tickets)}</p>"
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        "</body></html>\n"
    )


def write_report(
    tickets: list[Ticket],
    project: str,
    start: date,
    end: date,
    folder: Path,
    formats: tuple[str, ...],
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / f"status-report-{project}-{start}"
    paths = []
    if "markdown" in formats:
        path = base.with_suffix(".md")
        path.write_text(to_markdown(tickets, project, start, end), encoding="utf-8")
        paths.append(path)
    if "html" in formats:
        path = base.with_suffix(".html")
        path.write_text(to_html(tickets, project, start, end), encoding="utf-8")
        paths.append(path)
    return paths
