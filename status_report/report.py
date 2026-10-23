"""Writes the report files.

Markdown (SRG-27, D45): header, project status, executive summary, key numbers,
priority matrix, blocked, overdue, closed this week, next week, then warnings and
all tickets. The HTML layout comes in SRG-28.
Each status is a colour mark and a word, never a colour only (D21, accessibility).
File name: <project>-<ISO year>-W<ISO week>, for example SRG-2026-W43.md.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from status_report.ai import Summary
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
MD_SECTIONS = (
    "Project status", "Executive summary", "Key numbers", "Priority matrix", "Blocked tickets",
    "Overdue tickets", "Closed this week", "Next week", "All tickets",
)
HTML_SECTIONS = ("Project status", "Weekly numbers", "Priority matrix", "Tickets")  # SRG-28
MARKS = {"Black": "⚫", "Red": "🔴", "Amber": "🟠", "Green": "🟢", "Done": "✅"}
NOT_AVAILABLE = "_Not available in this report. See Warnings._"
NONE = "None."
AI_NOTE = "Written by AI from the facts in this report. The rules set the status, not the AI (D02)."


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


def report_name(project: str, start: date) -> str:
    """File name without the suffix, for example SRG-2026-W43 (SRG-27)."""
    year, week, _ = start.isocalendar()
    return f"{project}-{year}-W{week:02d}"


def marked(status: str) -> str:
    """A status as a colour mark and a word, for example "🔴 Red" (D21)."""
    mark = MARKS.get(status)
    return f"{mark} {status}" if mark else status


def _owner(ticket: Ticket) -> str:
    return ticket.assignee or "Unassigned"


def _by_key(tickets: list[Ticket]) -> dict[str, Ticket]:
    return {t.key: t for t in tickets}


def _blocked_list(tickets: list[Ticket], metrics: WeekMetrics) -> list[tuple[str, ...]]:
    found = _by_key(tickets)
    keys = [k for k in metrics.blocked if k in found]
    keys.sort(key=lambda k: -(metrics.days_blocked.get(k) or 0))  # Longest first
    return [
        (k, found[k].title, _owner(found[k]), found[k].priority or "-",
         "n/a" if metrics.days_blocked.get(k) is None else str(metrics.days_blocked[k]))
        for k in keys
    ]


def _overdue_list(tickets: list[Ticket], metrics: WeekMetrics) -> list[tuple[str, ...]]:
    found = _by_key(tickets)
    rows = [found[k] for k in metrics.overdue if k in found and found[k].due_date]
    rows.sort(key=lambda t: (t.due_date, t.key))  # Oldest due date first
    today = metrics.today
    return [
        (t.key, t.title, _owner(t), t.priority or "-", t.due_date.isoformat(),
         str((today - t.due_date).days) if today else "-")
        for t in rows
    ]


def _closed_list(tickets: list[Ticket], metrics: WeekMetrics) -> list[tuple[str, ...]]:
    found = _by_key(tickets)
    return [
        (k, found[k].title, found[k].work_type, _owner(found[k]), found[k].priority or "-")
        for k in metrics.closed if k in found
    ]


# --- Markdown -------------------------------------------------------------------

def _md_text(value: object) -> str:
    """Text from Jira or the AI, safe for one Markdown line (SRG-35).

    "<", ">", and "&" become HTML entities, so raw HTML shows as text.
    Line breaks become spaces, so a table row stays on one line.
    """
    text = html.escape(str(value), quote=False)
    return " ".join(text.splitlines()) if text else text


def _md_cell(value: object) -> str:
    return _md_text(value).replace("|", "\\|")


def _md_table(columns, rows) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append("| " + " | ".join(_md_cell(c) for c in row) + " |")
    return lines


def _md_section(title: str, table: list[str]) -> list[str]:
    return ["", f"## {title}", "", *(table or [NONE])]


def to_markdown(
    tickets: list[Ticket],
    metrics: WeekMetrics,
    status: ProjectStatus,
    project: str,
    summary: Summary | None = None,
    warnings: list[str] | None = None,
    generated: date | None = None,
) -> str:
    """The Markdown report (SRG-27, D45). Each section is in the agreed order."""
    warnings = status.warnings if warnings is None else warnings
    week = metrics.start.isocalendar()[1]
    header = f"Week {week}: {metrics.start} to {metrics.end}"
    if generated:
        header += f" · Report date: {generated}"

    def table(columns, rows):
        return _md_table(columns, rows) if rows else []

    lines = [
        f"# Weekly Status Report: {_md_text(project)}",
        "",
        header,
        "",
        "## Project status",
        "",
        f"{MARKS.get(status.status, '')} **{status.status.upper()}** – {_md_text(status.reason)}",
        "",
        "## Executive summary",
        "",
    ]
    if summary is not None:
        lines += [_md_text(summary.text), "", f"_{AI_NOTE}_"]
    else:
        lines += [NOT_AVAILABLE]
    lines += _md_section("Key numbers", _md_table(("Number", "Value"), _number_rows(metrics)))
    matrix = [(marked(row[0]), *row[1:]) for row in _matrix_rows(status)]
    lines += _md_section("Priority matrix", _md_table(("Status", *LEVELS), matrix))
    lines += _md_section("Blocked tickets", table(
        ("Key", "Title", "Owner", "Priority", "Days blocked"), _blocked_list(tickets, metrics)))
    lines += _md_section("Overdue tickets", table(
        ("Key", "Title", "Owner", "Priority", "Due", "Days overdue"), _overdue_list(tickets, metrics)))
    lines += _md_section("Closed this week", table(
        ("Key", "Title", "Type", "Owner", "Priority"), _closed_list(tickets, metrics)))
    lines += ["", "## Next week", ""]
    if summary is not None:
        lines += [f"- {_md_text(item)}" for item in summary.next_week]
    else:
        lines += [NOT_AVAILABLE]
    if warnings:
        lines += ["", "## Warnings", "", *(f"- {_md_text(w)}" for w in warnings)]
    rows = [(r[0], r[1], r[2], marked(r[3]), *r[4:]) for r in _ticket_rows(tickets, status)]
    lines += _md_section("All tickets", table(COLUMNS, rows))
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
    tickets: list[Ticket],
    metrics: WeekMetrics,
    status: ProjectStatus,
    project: str,
    summary: Summary | None = None,
    warnings: list[str] | None = None,
) -> str:
    warnings = status.warnings if warnings is None else warnings
    title = html.escape(f"Weekly Status Report: {project}")
    parts = [
        "<!doctype html>\n<html><head><meta charset='utf-8'>",
        f"<title>{title}</title></head><body>",
        f"<h1>{title}</h1><p>Week: {metrics.start} to {metrics.end}</p>",
        "<h2>Project status</h2>",
        f"<p><strong>{html.escape(status.status.upper())}</strong> – {html.escape(status.reason)}</p>",
    ]
    if summary is not None:
        items = "".join(f"<li>{html.escape(i)}</li>" for i in summary.next_week)
        parts += [
            "<h2>Executive summary</h2>",
            f"<p>{html.escape(summary.text)}</p>",
            f"<p><strong>Next week</strong></p><ul>{items}</ul>",
            f"<p><em>{html.escape(AI_NOTE)}</em></p>",
        ]
    parts += [
        "<h2>Weekly numbers</h2>",
        _html_table(("Number", "Value"), _number_rows(metrics)),
        "<h2>Priority matrix</h2>",
        _html_table(("Status", *LEVELS), _matrix_rows(status)),
    ]
    if metrics.days_blocked:
        parts += ["<h2>Blocked tickets</h2>", _html_table(("Key", "Days blocked"), _blocked_rows(metrics))]
    if warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in warnings)
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
    summary: Summary | None = None,
    warnings: list[str] | None = None,
    generated: date | None = None,
) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / report_name(project, metrics.start)
    paths = []
    if "markdown" in formats:
        path = base.with_suffix(".md")
        path.write_text(to_markdown(tickets, metrics, status, project, summary, warnings, generated), encoding="utf-8")
        paths.append(path)
    if "html" in formats:
        path = base.with_suffix(".html")
        path.write_text(to_html(tickets, metrics, status, project, summary, warnings), encoding="utf-8")
        paths.append(path)
    return paths
