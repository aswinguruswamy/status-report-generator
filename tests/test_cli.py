"""Tests for the command line (SRG-18)."""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from status_report.cli import EXIT_ERROR, EXIT_OK, last_full_week, main, week_range
from status_report.jira_client import JiraError
from status_report.models import Ticket

REPO_CONFIG = str(Path(__file__).resolve().parent.parent / "config.yaml")


def ticket(key="SRG-1", title="Read tickets | Jira"):
    return Ticket(
        key=key, title=title, work_type="Story", status="To Do", status_category="To Do",
        priority="High", assignee="Person A", due_date=date(2026, 10, 24),
        created=datetime(2026, 10, 20, tzinfo=UTC), done_date=None, resolved=None,
    )


class FakeClient:
    def __init__(self, tickets=None, error=None):
        self.tickets = tickets or []
        self.error = error
        self.request = None

    def connect(self):
        if self.error:
            raise self.error
        return "Aswin"

    def fetch_tickets(self, project, work_types, start, end, need_flag=False):
        self.request = (project, work_types, start, end)
        return self.tickets


def run(tmp_path, *args, client=None, today=date(2026, 10, 22)):
    argv = ["--config", REPO_CONFIG, "--output", str(tmp_path), *args]
    return main(argv, client=client or FakeClient([ticket()]), today=today)


# --- Week rules ---------------------------------------------------------------

def test_week_range_is_monday_to_sunday():
    assert week_range(date(2026, 10, 22)) == (date(2026, 10, 19), date(2026, 10, 25))
    assert week_range(date(2026, 10, 19)) == (date(2026, 10, 19), date(2026, 10, 25))
    assert week_range(date(2026, 10, 25)) == (date(2026, 10, 19), date(2026, 10, 25))


def test_last_full_week_is_the_week_before():
    assert last_full_week(date(2026, 10, 22)) == (date(2026, 10, 12), date(2026, 10, 18))
    assert last_full_week(date(2026, 10, 19)) == (date(2026, 10, 12), date(2026, 10, 18))


def test_no_week_given_uses_last_full_week(tmp_path):
    client = FakeClient([ticket()])
    assert run(tmp_path, client=client) == EXIT_OK
    assert client.request[2:] == (date(2026, 10, 12), date(2026, 10, 18))


def test_week_option(tmp_path):
    client = FakeClient([ticket()])
    run(tmp_path, "--week", "2026-10-21", client=client)
    assert client.request[2:] == (date(2026, 10, 19), date(2026, 10, 25))


def test_project_option_overrides_config(tmp_path):
    client = FakeClient([ticket()])
    run(tmp_path, "--project", "ABC", client=client)
    assert client.request[0] == "ABC"


# --- Output -------------------------------------------------------------------

def test_both_formats_and_report_path_is_shown(tmp_path, capsys):
    assert run(tmp_path, "--week", "2026-10-19", "--format", "both") == EXIT_OK
    md = tmp_path / "SRG-2026-W43.md"
    page = tmp_path / "SRG-2026-W43.html"
    assert md.is_file() and page.is_file()
    out = capsys.readouterr().out
    assert "1/3" in out and "2/3" in out and "3/3" in out
    assert f"Report: {md.resolve()}" in out


def test_md_format_only(tmp_path):
    run(tmp_path, "--week", "2026-10-19", "--format", "md")
    assert [p.suffix for p in tmp_path.iterdir()] == [".md"]


def test_markdown_escapes_the_table_separator(tmp_path):
    run(tmp_path, "--week", "2026-10-19", "--format", "md")
    text = (tmp_path / "SRG-2026-W43.md").read_text()
    assert "Read tickets \\| Jira" in text


def test_html_escapes_ticket_titles(tmp_path):
    client = FakeClient([ticket(title="<script>x</script>")])
    run(tmp_path, "--week", "2026-10-19", "--format", "html", client=client)
    text = (tmp_path / "SRG-2026-W43.html").read_text()
    assert "<script>" not in text and "&lt;script&gt;" in text


def test_no_ai_option(tmp_path, capsys):
    run(tmp_path, "--no-ai")
    assert "AI summary: off" in capsys.readouterr().out


# --- Errors and exit codes ----------------------------------------------------

def test_jira_error_returns_error_code(tmp_path, capsys):
    client = FakeClient(error=JiraError("Jira refused the token (401)."))
    assert run(tmp_path, client=client) == EXIT_ERROR
    assert "ERROR: Jira refused the token" in capsys.readouterr().err


def test_config_error_returns_error_code(tmp_path, capsys):
    argv = ["--config", str(tmp_path / "missing.yaml")]
    assert main(argv, client=FakeClient()) == EXIT_ERROR
    assert "file not found" in capsys.readouterr().err


def test_wrong_option_value_stops_with_code_2(tmp_path):
    with pytest.raises(SystemExit) as stop:
        run(tmp_path, "--format", "pdf")
    assert stop.value.code == 2


def test_help_lists_all_options(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--help"])
    assert stop.value.code == 0
    out = capsys.readouterr().out
    for option in ["--project", "--week", "--output", "--format", "--no-ai", "--config"]:
        assert option in out


def test_report_and_progress_show_the_weekly_numbers(tmp_path, capsys):
    run(tmp_path, "--week", "2026-10-19", "--format", "md")
    out = capsys.readouterr().out
    assert "closed 0, opened 1, open 1, blocked 0, overdue 0" in out
    text = (tmp_path / "SRG-2026-W43.md").read_text()
    assert "## Key numbers" in text
    assert "| Opened this week | 1 |" in text


def test_command_depends_on_the_interface_not_on_jira():
    # D01: a second source (GitHub, v2) needs no change in the command.
    from status_report import cli

    assert not hasattr(cli, "JiraClient")
    assert hasattr(cli, "TicketSource")


def test_report_shows_project_status_matrix_and_ticket_status(tmp_path, capsys):
    run(tmp_path, "--week", "2026-10-19", "--format", "both")
    out = capsys.readouterr().out
    # SRG-1 is P2, due in 2 days, and still in To Do: Amber (D22).
    assert ("Project status: Amber: 1 P2 ticket is due soon and not started (SRG-1); "
            "the team closed 0 and opened 1 tickets.") in out
    text = (tmp_path / "SRG-2026-W43.md").read_text()
    for section in ("## Project status", "## Key numbers", "## Priority matrix", "## All tickets"):
        assert section in text
    assert "**AMBER** – Amber:" in text
    assert "| SRG-1 | Read tickets \\| Jira | Story | 🟠 Amber | To Do | High | 2026-10-24 |" in text
    page = (tmp_path / "SRG-2026-W43.html").read_text()
    assert "<h2>Priority matrix</h2>" in page and "<strong>AMBER</strong>" in page


def test_report_has_the_ai_summary_when_the_ai_answers(tmp_path, capsys):
    from test_ai import FakeClient as FakeAI

    answer = {
        "summary": "The project is Amber. SRG-1 is due soon and not started. No ticket was closed.",
        "next_week": ["Start SRG-1."],
    }
    fake = FakeAI(answer)
    argv = ["--config", REPO_CONFIG, "--output", str(tmp_path), "--week", "2026-10-19", "--format", "md"]
    assert main(argv, client=FakeClient([ticket()]), today=date(2026, 10, 22), ai_client=fake) == EXIT_OK
    text = (tmp_path / "SRG-2026-W43.md").read_text()
    assert "## Executive summary\n\nThe project is Amber." in text
    assert "_Not available" not in text and "- Start SRG-1." in text
    assert "The rules set the status, not the AI" in text
    assert "AI summary: done (900 + 120 tokens)" in capsys.readouterr().out


def test_ai_answer_with_unknown_key_is_removed_with_a_warning(tmp_path):
    from test_ai import FakeClient as FakeAI

    answer = {"summary": "The project is Amber. SRG-77 is late. One more point.",
              "next_week": ["Fix SRG-77."]}
    argv = ["--config", REPO_CONFIG, "--output", str(tmp_path), "--week", "2026-10-19", "--format", "md"]
    main(argv, client=FakeClient([ticket()]), today=date(2026, 10, 22), ai_client=FakeAI(answer))
    text = (tmp_path / "SRG-2026-W43.md").read_text()
    assert "## Executive summary\n\n_Not available in this report. See Warnings._" in text
    assert "No AI summary in this report. The AI summary names tickets that are not in the input: SRG-77." in text

