"""The portfolio report (spec SRG-R12.1, SRG-R12.2, SRG-R14.2, N9; AC34, AC35, AC36; plan S8)."""

from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from v2_tickets import CONFIG, NOW, ticket

from status_report.jira_client import JiraError
from status_report.models import TeamData
from status_report.portfolio import build_portfolio
from status_report.report import report_name, to_markdown, write_report
from status_report.run import load_settings, make_client, read_portfolio

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "examples" / "SRG_2026-12-01_0942.md"


def data(key, tickets, browse="https://site.example/browse/"):
    from v2_tickets import SPRINT

    return TeamData(key, tuple(tickets), (SPRINT,), None, None, NOW, browse)


def portfolio(alpha=(), beta=(), sample=False, read_at=NOW):
    results = {"ALP": data("ALP", alpha), "BET": beta if isinstance(beta, Exception) else data("BET", beta)}
    return build_portfolio(CONFIG, results, read_at, sample=sample)


def demo_portfolio():
    config = load_settings(demo=True)
    return read_portfolio(make_client(demo=True), config, demo=True, at_start=True)


def section(text: str, title: str) -> str:
    return text.split(f"## {title}", 1)[1].split("\n## ", 1)[0]


# --- AC34: file name and content from the same data (golden file) ------------------------------


def test_ac34_file_name_has_the_read_date_and_time(tmp_path):
    read_at = datetime(2026, 12, 1, 14, 42, tzinfo=UTC)  # 09:42 in Toronto
    table = portfolio(read_at=read_at)
    assert report_name(table) == "SRG_2026-12-01_0942.md"
    path = write_report(table, tmp_path / "output")
    assert path.name == "SRG_2026-12-01_0942.md" and path.read_text(encoding="utf-8") == to_markdown(table)


def test_ac34_golden_file_matches_the_demo_report():
    spec = importlib.util.spec_from_file_location("make_sample", ROOT / "scripts" / "make_sample.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = module.build()
    assert list(expected) == ["SRG_2026-12-01_0942.md"]
    assert GOLDEN.read_text(encoding="utf-8") == expected[GOLDEN.name], (
        "examples/ is old. Run: python scripts/make_sample.py"
    )


def test_ac34_report_content_equals_the_page_data():
    table = demo_portfolio()
    text = to_markdown(table)
    assert "As of 2026-12-01 09:42 (America/Toronto)" in text
    for row in table.rows:
        assert f"| {row.name} |" in text and row.reason in text and row.progress in text
        assert row.forecast.text in text
        assert f"## {row.name} – " in text
        for problem in row.problems:
            assert f"| {problem.key} | {problem.title} |" in text


# --- AC35: Black, Red and Amber tickets under each team --------------------------------------


def test_ac35_two_red_tickets_are_both_listed_under_beta():
    beta = [ticket("BET-2", priority="Highest", status="Blocked", due=9),
            ticket("BET-5", priority="Low", status="Blocked", due=9),
            ticket("BET-8", priority="Low", due=9)]  # Green: not listed
    text = to_markdown(portfolio(beta=beta))
    beta_part = section(text, "Beta – 🔴 Red")
    assert "[BET-2](https://site.example/browse/BET-2)" in beta_part
    assert "[BET-5](https://site.example/browse/BET-5)" in beta_part
    assert "BET-8" not in beta_part
    assert "| Highest | 🔴 Red | Blocked |" in beta_part


def test_team_without_problem_tickets_says_so():
    text = to_markdown(portfolio(beta=[ticket("BET-1", due=9)]))
    assert "No Black, Red or Amber tickets." in section(text, "Beta – 🟢 Green")


# --- Sample data label (R14.2, AC36) and errors (N4.1) -------------------------------------------


def test_ac36_sample_data_label_only_in_demo_mode():
    assert "**Sample data.**" in to_markdown(portfolio(sample=True))
    assert "Sample data" not in to_markdown(portfolio(sample=False))


def test_sample_data_has_no_links():
    text = GOLDEN.read_text(encoding="utf-8")
    assert "](" not in text and "**Sample data.**" in text


def test_team_that_could_not_be_read_is_in_the_report():
    text = to_markdown(portfolio(beta=JiraError("Jira error 500 on /rest/api/3/project/BET.")))
    assert "| Beta | Could not read | – | – | Could not read – Jira error 500" in text
    assert "## Beta – Could not read" in text


# --- Safe text and accessibility (N9) ------------------------------------------------------------


def test_titles_cannot_break_the_markdown():
    bad = replace(ticket("BET-1", priority="Highest", status="Blocked", due=9),
                  title="Line one\nline two | <script>x</script>")
    text = to_markdown(portfolio(beta=[bad]))
    assert "Line one line two \\| &lt;script&gt;x&lt;/script&gt;" in text
    assert "<script>" not in text


def test_every_colour_has_a_word():
    text = GOLDEN.read_text(encoding="utf-8")
    for mark, word in (("⚫", "Black"), ("🔴", "Red"), ("🟠", "Amber"), ("🟢", "Green")):
        assert f"{mark} {word}" in text


def test_warnings_section():
    text = to_markdown(portfolio(beta=[ticket("BET-3", priority="Urgent", due=9)]))
    assert "## Warnings" in text and "BET-3: priority 'Urgent'" in section(text, "Warnings")


def test_no_html_report_any_more():
    from status_report import report

    assert not hasattr(report, "to_html")


def test_markdown_signs_in_titles_show_as_text():  # S8 review
    bad = replace(ticket("BET-1", priority="Highest", status="Blocked", due=9),
                  title="[Approve](https://evil.example) *bold* _x_ `code` back\\")
    text = to_markdown(portfolio(beta=[bad]))
    assert "\\[Approve\\](https://evil.example) \\*bold\\* \\_x\\_ \\`code\\` back\\\\" in text
    assert "[Approve](" not in text


def test_demo_without_the_sample_files_gives_a_clear_error(monkeypatch, tmp_path):  # S8 review
    import pytest

    from status_report import demo
    from status_report.config import ConfigError

    monkeypatch.setattr(demo, "CONFIG_FILE", tmp_path / "missing.yaml")
    with pytest.raises(ConfigError, match="Run the demo from a copy of the repository"):
        load_settings(demo=True)
