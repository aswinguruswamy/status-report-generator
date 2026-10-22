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
    md = tmp_path / "status-report-SRG-2026-10-19.md"
    page = tmp_path / "status-report-SRG-2026-10-19.html"
    assert md.is_file() and page.is_file()
    out = capsys.readouterr().out
    assert "1/3" in out and "2/3" in out and "3/3" in out
    assert f"Report: {md.resolve()}" in out


def test_md_format_only(tmp_path):
    run(tmp_path, "--week", "2026-10-19", "--format", "md")
    assert [p.suffix for p in tmp_path.iterdir()] == [".md"]


def test_markdown_escapes_the_table_separator(tmp_path):
    run(tmp_path, "--week", "2026-10-19", "--format", "md")
    text = (tmp_path / "status-report-SRG-2026-10-19.md").read_text()
    assert "Read tickets \\| Jira" in text


def test_html_escapes_ticket_titles(tmp_path):
    client = FakeClient([ticket(title="<script>x</script>")])
    run(tmp_path, "--week", "2026-10-19", "--format", "html", client=client)
    text = (tmp_path / "status-report-SRG-2026-10-19.html").read_text()
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
