"""Writes the report files.

build_sections() makes the content once. to_markdown (SRG-27, D45) and to_html
(SRG-28, D46) only format it, so both files have the same sections and data:
header, project status, executive summary, key numbers, priority matrix, blocked,
overdue, closed this week, next week, then warnings and all tickets.
Each status is a colour mark and a word, never a colour only (D21, accessibility).
File name: <project>-<ISO year>-W<ISO week>, for example SRG-2026-W43.md.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
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
MARKS = {"Black": "⚫", "Red": "🔴", "Amber": "🟠", "Green": "🟢", "Done": "✅"}
NOT_AVAILABLE_TEXT = "Not available in this report. See Warnings."
NOT_AVAILABLE = f"_{NOT_AVAILABLE_TEXT}_"  # In Markdown
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


# --- Shared content: both formats show the same sections and data (SRG-28, D46) ---

@dataclass(frozen=True)
class Mark:
    """A status cell. Markdown shows "🔴 Red"; HTML shows a coloured badge with the word."""

    status: str


@dataclass(frozen=True)
class Section:
    title: str
    columns: tuple[str, ...] = ()  # A table when not empty
    rows: tuple[tuple, ...] = ()
    items: tuple[str, ...] = ()  # A list
    text: tuple[str, ...] = ()  # Paragraphs
    note: str = ""  # Shown in italics after the text
    empty: str = ""  # Shown when there is no table row, item, or text


def build_sections(
    tickets: list[Ticket],
    metrics: WeekMetrics,
    status: ProjectStatus,
    summary: Summary | None,
    warnings: list[str],
) -> list[Section]:
    """The report content, in the agreed order (D45). The renderers only format it."""
    def marks(rows, column):
        return tuple((*r[:column], Mark(r[column]), *r[column + 1:]) for r in rows)

    sections = [
        Section("Project status", text=(status.reason,)),
        Section("Executive summary", text=(summary.text,) if summary else (),
                note=AI_NOTE if summary else "", empty=NOT_AVAILABLE_TEXT),
        Section("Key numbers", ("Number", "Value"), tuple(_number_rows(metrics))),
        Section("Priority matrix", ("Status", *LEVELS), marks(_matrix_rows(status), 0)),
        Section("Blocked tickets", ("Key", "Title", "Owner", "Priority", "Days blocked"),
                tuple(_blocked_list(tickets, metrics)), empty=NONE),
        Section("Overdue tickets", ("Key", "Title", "Owner", "Priority", "Due", "Days overdue"),
                tuple(_overdue_list(tickets, metrics)), empty=NONE),
        Section("Closed this week", ("Key", "Title", "Type", "Owner", "Priority"),
                tuple(_closed_list(tickets, metrics)), empty=NONE),
        Section("Next week", items=tuple(summary.next_week) if summary else (),
                empty=NOT_AVAILABLE_TEXT),
    ]
    if warnings:
        sections.append(Section("Warnings", items=tuple(warnings)))
    sections.append(Section("All tickets", COLUMNS, marks(_ticket_rows(tickets, status), 3), empty=NONE))
    return sections


def _header(project: str, metrics: WeekMetrics, generated: date | None) -> tuple[str, str]:
    week = metrics.start.isocalendar()[1]
    line = f"Week {week}: {metrics.start} to {metrics.end}"
    if generated:
        line += f" · Report date: {generated}"
    return f"Weekly Status Report: {project}", line


# --- Markdown -------------------------------------------------------------------

def _md_value(cell) -> str:
    return marked(cell.status) if isinstance(cell, Mark) else cell


def to_markdown(
    tickets: list[Ticket],
    metrics: WeekMetrics,
    status: ProjectStatus,
    project: str,
    summary: Summary | None = None,
    warnings: list[str] | None = None,
    generated: date | None = None,
) -> str:
    """The Markdown report (SRG-27, D45)."""
    warnings = status.warnings if warnings is None else warnings
    title, header = _header(project, metrics, generated)
    lines = [f"# {_md_text(title)}", "", header]
    for sec in build_sections(tickets, metrics, status, summary, warnings):
        lines += ["", f"## {sec.title}", ""]
        if sec.title == "Project status":
            lines.append(
                f"{MARKS.get(status.status, '')} **{status.status.upper()}** – {_md_text(status.reason)}"
            )
            continue
        body = []
        if sec.rows:
            body += _md_table(sec.columns, [tuple(_md_value(c) for c in r) for r in sec.rows])
        body += [f"- {_md_text(i)}" for i in sec.items]
        for paragraph in sec.text:
            body += [_md_text(paragraph)]
        if sec.note:
            body += ["", f"_{sec.note}_"]
        lines += body or [f"_{sec.empty}_" if sec.empty == NOT_AVAILABLE_TEXT else sec.empty]
    return "\n".join(lines) + "\n"


# --- HTML -----------------------------------------------------------------------

CSS = """
:root{--ink:#1a1a1a;--muted:#555;--line:#c8c8c8;--bg:#fff}
*{box-sizing:border-box}
body{margin:0 auto;max-width:980px;padding:16px;font:15px/1.5 -apple-system,"Segoe UI",
Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.1rem;margin:28px 0 8px;
border-bottom:2px solid var(--ink);padding-bottom:2px}
.meta,.note{color:var(--muted)}.note{font-style:italic;font-size:.9rem}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{background:#f0f0f0}td{overflow-wrap:break-word}
table.wide{min-width:640px}td:first-child{white-space:nowrap}
.st{display:inline-block;padding:1px 8px;border-radius:10px;border:2px solid;font-weight:700;
white-space:nowrap}
.st::before{margin-right:4px}
.st-black{background:#1a1a1a;color:#fff;border-color:#1a1a1a}.st-black::before{content:"■"}
.st-red{background:#fde2e1;color:#8a1111;border-color:#c62828}.st-red::before{content:"●"}
.st-amber{background:#fff1d6;color:#7a4a00;border-color:#e08e00}.st-amber::before{content:"▲"}
.st-green{background:#e3f4e5;color:#1b5e20;border-color:#2e7d32}.st-green::before{content:"◆"}
.st-done{background:#eceff1;color:#37474f;border-color:#78909c}.st-done::before{content:"✓"}
.status{font-size:1.05rem}
@media print{body{max-width:none;padding:0;font-size:11pt}table.wide{min-width:0}
h2{break-after:avoid}tr{break-inside:avoid}.wrap{overflow:visible}
.st{background:#fff!important;color:#000!important;border-color:#000!important}
.st-black{border-style:double}}
"""


def _badge(status: str) -> str:
    return f'<span class="st st-{html.escape(status.lower())}">{html.escape(status)}</span>'


def _html_cell(cell) -> str:
    return _badge(cell.status) if isinstance(cell, Mark) else html.escape(str(cell))


def _html_table(columns, rows) -> str:
    head = "".join(f"<th scope='col'>{html.escape(c)}</th>" for c in columns)
    body = "".join("<tr>" + "".join(f"<td>{_html_cell(c)}</td>" for c in row) + "</tr>" for row in rows)
    wide = " class='wide'" if len(columns) > 3 else ""  # Scrolls on a phone, no broken words
    return f"<div class='wrap'><table{wide}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def to_html(
    tickets: list[Ticket],
    metrics: WeekMetrics,
    status: ProjectStatus,
    project: str,
    summary: Summary | None = None,
    warnings: list[str] | None = None,
    generated: date | None = None,
) -> str:
    """One HTML file with no external links (SRG-28, D46). Same content as the Markdown."""
    warnings = status.warnings if warnings is None else warnings
    title, header = _header(project, metrics, generated)
    parts = [
        "<!doctype html>\n<html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body>",
        f"<h1>{html.escape(title)}</h1><p class='meta'>{html.escape(header)}</p>",
    ]
    for sec in build_sections(tickets, metrics, status, summary, warnings):
        parts.append(f"<h2>{html.escape(sec.title)}</h2>")
        if sec.title == "Project status":
            parts.append(f"<p class='status'>{_badge(status.status)} {html.escape(status.reason)}</p>")
            continue
        body = []
        if sec.rows:
            body.append(_html_table(sec.columns, sec.rows))
        if sec.items:
            body.append("<ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in sec.items) + "</ul>")
        body += [f"<p>{html.escape(t)}</p>" for t in sec.text]
        if sec.note:
            body.append(f"<p class='note'>{html.escape(sec.note)}</p>")
        parts += body or [f"<p class='note'>{html.escape(sec.empty)}</p>"]
    parts.append("</body></html>\n")
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
    args = (tickets, metrics, status, project, summary, warnings, generated)
    paths = []
    if "markdown" in formats:
        path = base.with_suffix(".md")
        path.write_text(to_markdown(*args), encoding="utf-8")
        paths.append(path)
    if "html" in formats:
        path = base.with_suffix(".html")
        path.write_text(to_html(*args), encoding="utf-8")
        paths.append(path)
    return paths
