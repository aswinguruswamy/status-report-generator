"""The portfolio report: one Markdown file (spec SRG-R12.1, SRG-R12.2, SRG-R14.2; plan S8).

The report shows the same data as the page: the "as of" time, the team table, the reason for
each team, and each team's Black, Red and Amber tickets. It makes no rule decision of its own.
Each colour is a mark and a word, never a colour only (spec N9).
File name: SRG_<yyyy-mm-dd>_<hhmm>.md, with the Jira read time (local time).
"""

from __future__ import annotations

import html
from pathlib import Path
from zoneinfo import ZoneInfo

from status_report.portfolio import Portfolio, TeamRow

MARKS = {"Black": "⚫", "Red": "🔴", "Amber": "🟠", "Green": "🟢"}
SAMPLE_NOTE = "**Sample data.** The teams and tickets are made up."
NO_PROBLEMS = "No Black, Red or Amber tickets."
TABLE_COLUMNS = ("Team", "Colour", "Done/total", "Forecast", "Reason")
DETAIL_COLUMNS = ("Key", "Title", "Priority", "Colour", "Cause")


def marked(colour: str | None) -> str:
    """A colour as a mark and a word, for example "🔴 Red" (N9)."""
    if colour is None:
        return "Could not read"
    return f"{MARKS[colour]} {colour}"


def report_name(portfolio: Portfolio) -> str:
    """Spec R12.2: SRG_<yyyy-mm-dd>_<hhmm>.md with the read time."""
    local = portfolio.read_at.astimezone(ZoneInfo(portfolio.timezone))
    return f"SRG_{local:%Y-%m-%d}_{local:%H%M}.md"


MARKDOWN_SIGNS = "\\`*_[]"  # Backslash first


def _text(value: object) -> str:
    """Text from Jira, safe for one Markdown line: HTML and Markdown signs show as text
    (no live link, no bold), and there are no line breaks."""
    text = " ".join(str(value).split())
    for sign in MARKDOWN_SIGNS:
        text = text.replace(sign, "\\" + sign)
    return html.escape(text, quote=False)


def _cell(value: object) -> str:
    return _text(value).replace("|", "\\|")


def _table(columns, rows) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _forecast(row: TeamRow) -> str:
    return _cell(row.forecast.text) if row.forecast else "–"


def _key(key: str, url: str | None) -> str:
    if not url:
        return _cell(key)
    safe = url.replace(" ", "%20").replace("(", "%28").replace(")", "%29")
    return f"[{_cell(key)}]({safe})"


def _team_section(row: TeamRow) -> list[str]:
    lines = ["", f"## {_text(row.name)} – {marked(row.colour)}", "", _text(row.reason)]
    if row.error:
        return lines
    facts = [t for t in (row.no_due_text, row.window_text) if t]
    lines += ["", " · ".join(facts)]
    if not row.problems:
        return lines + ["", NO_PROBLEMS]
    rows = [
        (_key(p.key, p.url), _cell(p.title), _cell(p.priority), marked(p.colour), _cell(p.cause))
        for p in row.problems
    ]
    return lines + [""] + _table(DETAIL_COLUMNS, rows)


def to_markdown(portfolio: Portfolio) -> str:
    local = portfolio.read_at.astimezone(ZoneInfo(portfolio.timezone))
    lines = ["# Team status report", ""]
    if portfolio.sample:
        lines += [SAMPLE_NOTE, ""]
    lines += [f"As of {local:%Y-%m-%d %H:%M} ({portfolio.timezone}), the time of the Jira read.",
              "", "## Teams", ""]
    rows = [
        (_cell(r.name), marked(r.colour), _cell(r.progress), _forecast(r), _cell(r.reason))
        for r in portfolio.rows
    ]
    lines += _table(TABLE_COLUMNS, rows)
    for row in portfolio.rows:
        lines += _team_section(row)
    if portfolio.warnings:
        lines += ["", "## Warnings", ""] + [f"- {_text(w)}" for w in portfolio.warnings]
    return "\n".join(lines) + "\n"


def write_report(portfolio: Portfolio, folder: str | Path) -> Path:
    """Write the report file and return its path."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / report_name(portfolio)
    path.write_text(to_markdown(portfolio), encoding="utf-8")
    return path
