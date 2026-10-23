"""Tests for the HTML report (SRG-28, D46)."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date
from html.parser import HTMLParser

import pytest
from generator import WEEK_END, WEEK_START, make_week
from test_metrics import CONFIG
from test_report import SUMMARY, red_week

from status_report.metrics import calculate, tickets_in_week
from status_report.project import project_status
from status_report.report import MD_SECTIONS, to_html, to_markdown


def page(summary=SUMMARY, week=None):
    week_tickets, metrics, status = week or red_week()
    return to_html(week_tickets, metrics, status, "SRG", summary, generated=date(2026, 10, 26))


class Cells(HTMLParser):
    """Collects the text of each table cell, and each tag and attribute."""

    def __init__(self):
        super().__init__()
        self.cells, self.tags, self._cell = [], [], None

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag in ("td", "th"):
            self._cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self.cells.append(self._cell.strip())
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data


def parse(text: str) -> Cells:
    parser = Cells()
    parser.feed(text)
    return parser


def md_cells(markdown: str) -> list[str]:
    cells = []
    for line in markdown.splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            for cell in re.split(r"(?<!\\)\|", line)[1:-1]:
                text = cell.strip().replace("\\|", "|")
                cells.append(re.sub(r"^[⚫🔴🟠🟢✅] ", "", text))  # The mark is a badge in HTML
    return cells


def test_same_sections_in_the_same_order_as_markdown():
    assert re.findall(r"<h2>(.*?)</h2>", page()) == list(MD_SECTIONS)


def test_same_table_data_as_markdown():
    week_tickets, metrics, status = red_week()
    markdown = to_markdown(week_tickets, metrics, status, "SRG", SUMMARY)
    assert parse(page()).cells == md_cells(markdown)


def test_same_text_as_markdown():
    text = page()
    for part in (SUMMARY.text, "Free SRG-1.", "Week 43: 2026-10-19 to 2026-10-25 · Report date: 2026-10-26",
                 "Written by AI from the facts in this report."):
        assert part in text


def test_one_file_with_no_external_links():
    parsed = parse(page())
    tags = {tag for tag, _ in parsed.tags}
    assert not tags & {"script", "link", "img", "iframe", "object", "embed"}
    for _, attrs in parsed.tags:
        assert not {"src", "href"} & set(attrs)
    assert "http" not in page() and "@import" not in page() and "url(" not in page()


def test_each_status_cell_has_a_colour_and_a_word():
    text = page()
    matrix = text.split("<h2>Priority matrix</h2>")[1].split("<h2>")[0]
    for status in ("Black", "Red", "Amber", "Green"):
        assert f'<span class="st st-{status.lower()}">{status}</span>' in matrix
    for status in ("black", "red", "amber", "green", "done"):
        assert f".st-{status}{{background:" in text  # A colour for each status


def test_page_works_on_a_phone_and_in_black_and_white_print():
    text = page()
    assert "name='viewport' content='width=device-width, initial-scale=1'" in text
    assert ".wrap{overflow-x:auto}" in text  # Wide tables scroll on a phone
    assert "@media print" in text
    # In print, each badge is black on white and keeps its word and shape mark.
    assert ".st{background:#fff!important;color:#000!important" in text
    for shape in ("■", "●", "▲", "◆", "✓"):
        assert f'content:"{shape}"' in text


def test_special_characters_show_and_cannot_break_the_page():
    week_tickets, metrics, status = red_week()
    week_tickets = [replace(t, title='<script>alert(1)</script> & "quotes" Ünïcødé ✓\nline')
                    if t.key == "SRG-1" else t for t in week_tickets]
    text = page(week=(week_tickets, metrics, status))
    assert "<script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;quotes&quot; Ünïcødé ✓" in text
    parsed = parse(text)
    starts = sum(1 for tag, _ in parsed.tags if tag == "tr")
    assert starts == text.count("</tr>")  # Each row is closed: the structure is intact


def test_not_available_text_without_ai():
    text = page(summary=None)
    assert text.count("<p class='note'>Not available in this report. See Warnings.</p>") == 2


def _norm(cells):
    import html

    return [" ".join(html.unescape(c).split()) for c in cells]


@pytest.mark.parametrize("seed", range(0, 300, 3))
def test_random_weeks_have_the_same_data_in_both_formats(seed):
    week = make_week(seed)
    metrics = calculate(week, CONFIG, WEEK_START, WEEK_END)
    in_week = tickets_in_week(week, metrics)
    status = project_status(in_week, metrics, CONFIG)
    markdown = to_markdown(in_week, metrics, status, "SIM")
    text = to_html(in_week, metrics, status, "SIM")
    assert _norm(parse(text).cells) == _norm(md_cells(markdown))
