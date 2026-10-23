"""Tests for safe text in the Markdown report (SRG-35, D42).

B1: a line break in a title broke the table row.
B2: raw HTML in a title went into the .md file.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from test_metrics import CONFIG, ticket
from test_random import _table_rows_complete

from status_report.ai import Summary
from status_report.metrics import calculate
from status_report.project import project_status
from status_report.report import _md_cell, to_markdown

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
