"""Tests for the Markdown report: safe text (SRG-35, D42) and layout (SRG-27, D45).

B1: a line break in a title broke the table row.
B2: raw HTML in a title went into the .md file.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from test_metrics import CONFIG, at, change, ticket
from test_random import _table_rows_complete

from status_report.ai import Summary
from status_report.metrics import calculate, tickets_in_week
from status_report.project import project_status
from status_report.report import (
    MD_SECTIONS,
    NOT_AVAILABLE,
    _md_cell,
    report_name,
    to_markdown,
    write_report,
)

START, END = date(2026, 10, 19), date(2026, 10, 25)


def report(title: str, summary: Summary | None = None) -> str:
    tickets = [replace(ticket("SRG-1"), title=title)]
    metrics = calculate(tickets, CONFIG, START, END)
    status = project_status(tickets, metrics, CONFIG)
    return to_markdown(tickets, metrics, status, "SRG", summary=summary)


def ticket_row(markdown: str) -> str:
    return next(line for line in markdown.splitlines() if line.startswith("| SRG-1 "))


def test_line_break_in_a_title_keeps_one_row():  # B1
    markdown = report("Line one\nline two\r\nline three")
    assert "Line one line two line three" in ticket_row(markdown)
    assert _table_rows_complete(markdown)


def test_raw_html_in_a_title_shows_as_text():  # B2
    row = ticket_row(report("<script>alert(1)</script> <b>x</b>"))
    assert "<script>" not in row and "<b>" not in row
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &lt;b&gt;x&lt;/b&gt;" in row


def test_pipe_and_ampersand_are_escaped():
    assert _md_cell("A | B & C") == "A \\| B &amp; C"


def test_quotes_and_unicode_stay_as_they_are():
    assert _md_cell("Quote \" and ' — Ünïcødé ✓") == "Quote \" and ' — Ünïcødé ✓"


def test_ai_summary_and_next_week_are_safe_too():
    summary = Summary(
        text="The project is Red.\nSRG-1 is <b>blocked</b>. One closed.",
        next_week=("Free SRG-1 <img src=x>",),
    )
    markdown = report("Title", summary)
    assert "<b>" not in markdown and "<img" not in markdown
    assert "The project is Red. SRG-1 is &lt;b&gt;blocked&lt;/b&gt;. One closed." in markdown


def test_check_finds_a_broken_row():
    assert not _table_rows_complete("| A | B |\n|---|---|\n| 1 | 2 | 3 |")
    assert _table_rows_complete("| A | B |\n|---|---|\n| 1 \\| x | 2 |")


# --- Markdown layout (SRG-27, D45) ------------------------------------------------------

SUMMARY = Summary("The project is Red. SRG-1 is blocked. SRG-2 is overdue.", ("Free SRG-1.",))


def red_week():
    tickets = [
        replace(ticket("SRG-1", created=at(5), history=[change(at(20), "To Do", "Blocked")]),
                priority="Highest", title="Blocked work", assignee="Jane Doe"),
        replace(ticket("SRG-2", created=at(5), due=date(2026, 10, 21)),
                priority="High", title="Overdue work", assignee=None),
        replace(ticket("SRG-3", history=[change(at(21), "To Do", "Done")]),
                title="Closed work", assignee="Sam Lee"),
        replace(ticket("SRG-4", created=at(5)), title="Green work"),
    ]
    metrics = calculate(tickets, CONFIG, START, END)
    week = tickets_in_week(tickets, metrics)
    return week, metrics, project_status(week, metrics, CONFIG)


def md(summary=SUMMARY, **kwargs):
    week, metrics, status = red_week()
    return to_markdown(week, metrics, status, "SRG", summary, generated=date(2026, 10, 26), **kwargs)


def section(text: str, title: str) -> str:
    return text.split(f"## {title}\n", 1)[1].split("\n## ", 1)[0]


def test_sections_are_in_the_agreed_order():
    headings = [line[3:] for line in md().splitlines() if line.startswith("## ")]
    assert headings == list(MD_SECTIONS)


def test_header_has_project_week_and_report_date():
    lines = md().splitlines()
    assert lines[0] == "# Weekly Status Report: SRG"
    assert lines[2] == "Week 43: 2026-10-19 to 2026-10-25 · Report date: 2026-10-26"


def test_each_status_has_a_mark_and_a_word():  # D21
    text = md()
    assert "🔴 **RED** – Red:" in text
    for row in ("| ⚫ Black |", "| 🔴 Red |", "| 🟠 Amber |", "| 🟢 Green |"):
        assert row in section(text, "Priority matrix")
    assert "| SRG-3 | Closed work | Story | ✅ Done |" in section(text, "All tickets")


def test_blocked_list_has_key_title_owner_priority_and_days():
    blocked = section(md(), "Blocked tickets")
    assert "| Key | Title | Owner | Priority | Days blocked |" in blocked
    assert "| SRG-1 | Blocked work | Jane Doe | Highest | 5 |" in blocked


def test_overdue_and_closed_lists():
    text = md()
    assert "| SRG-2 | Overdue work | Unassigned | High | 2026-10-21 | 5 |" in section(text, "Overdue tickets")
    assert "| SRG-3 | Closed work | Story | Sam Lee | High |" in section(text, "Closed this week")
    assert "SRG-4" not in section(text, "Closed this week")


def test_empty_lists_say_none():
    tickets = [ticket("SRG-9", created=at(5))]
    metrics = calculate(tickets, CONFIG, START, END)
    text = to_markdown(tickets, metrics, project_status(tickets, metrics, CONFIG), "SRG")
    for title in ("Blocked tickets", "Overdue tickets", "Closed this week"):
        assert section(text, title).strip() == "None."


def test_summary_and_next_week_say_not_available_in_one_line():
    text = md(summary=None)
    assert section(text, "Executive summary").strip() == NOT_AVAILABLE
    assert section(text, "Next week").strip() == NOT_AVAILABLE


def test_next_week_comes_from_the_ai_summary():
    assert section(md(), "Next week").strip() == "- Free SRG-1."


def test_file_name_has_project_and_iso_week(tmp_path):
    assert report_name("SRG", date(2026, 10, 19)) == "SRG-2026-W43"
    assert report_name("SRG", date(2026, 12, 28)) == "SRG-2026-W53"  # 2026 has 53 ISO weeks
    assert report_name("ABC", date(2027, 1, 4)) == "ABC-2027-W01"
    week, metrics, status = red_week()
    paths = write_report(week, metrics, status, "SRG", tmp_path / "output", ("markdown",))
    assert [p.name for p in paths] == ["SRG-2026-W43.md"]


def test_output_folder_is_ignored_by_git():  # D24
    from pathlib import Path

    ignore = (Path(__file__).resolve().parent.parent / ".gitignore").read_text().splitlines()
    assert "output/" in ignore
