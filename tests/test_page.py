"""The web page (spec SRG-R3, R11, R12, R14, N4.2, N9; AC30, AC33, AC36, AC43; plan S9)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from v2_tickets import CONFIG, NOW, SPRINT, ticket

from status_report.jira_client import JiraError
from status_report.models import TeamData
from status_report.page import (
    SAMPLE_BANNER,
    PageState,
    detail_lines,
    detail_rows,
    headline,
    refresh,
    table_rows,
)
from status_report.portfolio import build_portfolio

ROOT = Path(__file__).resolve().parent.parent


def portfolio_at(hour, minute=0, beta=None):
    read_at = datetime(2026, 12, 1, hour + 5, minute, tzinfo=UTC)  # Toronto = UTC-5
    data = {"ALP": TeamData("ALP", (ticket("ALP-1", due=9),), (SPRINT,), None, None, read_at, None),
            "BET": beta or TeamData("BET", (ticket("BET-1", due=9),), (SPRINT,), None, None,
                                    read_at, "https://site.example/browse/")}
    return build_portfolio(CONFIG, data, read_at)


# --- Refresh and honest errors (R3, N4.2) -----------------------------------------------------


def test_refresh_shows_the_new_read_time():
    state = refresh(PageState(portfolio_at(9)), lambda: portfolio_at(10), NOW)
    assert headline(state) == "Team status as of 10:00" and state.error is None


def test_ac30_whole_refresh_fails_keeps_the_last_good_read():
    def broken():
        raise JiraError("Cannot reach Jira at https://site.example: ConnectionError.")

    state = refresh(PageState(portfolio_at(9)), broken, NOW)
    text = headline(state)
    assert "Last good read 09:00" in text and "Cannot reach Jira" in text
    assert "as of 10:00" not in text and "as of" not in text
    assert state.last_good.read_at.hour == 14  # The 09:00 read, not new data


def test_every_team_failing_is_a_whole_failure():
    def all_fail():
        data = {"ALP": JiraError("Jira error 500."), "BET": JiraError("Jira error 500.")}
        return build_portfolio(CONFIG, data, datetime(2026, 12, 1, 15, tzinfo=UTC))

    state = refresh(PageState(portfolio_at(9)), all_fail, NOW)
    assert headline(state) == "Could not refresh: Jira error 500. Last good read 09:00."


def test_one_team_failing_is_not_a_whole_failure():  # N4.1: the row shows the error
    state = refresh(PageState(portfolio_at(9)), lambda: portfolio_at(10, beta=JiraError("busy")), NOW)
    assert state.error is None
    assert any(r["Reason"] == "Could not read – busy" for r in table_rows(state.last_good))


# --- Table and details (R1, R11, N9) -------------------------------------------------------------


def test_table_rows_show_every_colour_as_a_word():
    rows = table_rows(portfolio_at(9))
    assert rows[0] == {"Team": "Alpha", "Colour": "🟢 Green", "Done/total": "0/1",
                       "Forecast": "Not enough history yet – needs 12 weeks", "Reason": "Green: No blocked, overdue, or at-risk tickets."}


def test_ac33_details_order_and_window_line():
    tickets = (ticket("BET-9", priority="Medium", due=1),
               ticket("BET-2", priority="Highest", status="Blocked", due=9),
               ticket("BET-5", priority="High", status="Blocked", due=9))
    beta = TeamData("BET", tickets, (SPRINT,), None, None, NOW, "https://site.example/browse/")
    row = next(r for r in portfolio_at(9, beta=beta).rows if r.key == "BET")
    assert [r["Key"] for r in detail_rows(row)] == ["BET-2", "BET-5", "BET-9"]
    assert detail_rows(row)[0]["Link"] == "https://site.example/browse/BET-2"  # R11.3
    assert detail_lines(row)[-1] == "Closed 0 · Opened 0 in the last 14 days"


# --- The Streamlit page in demo mode (AC36, AC43) -----------------------------------------------


def test_ac36_ac43_demo_page_opens_fast_with_sample_data_and_no_token(monkeypatch):
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    started = time.perf_counter()
    at = AppTest.from_file(str(ROOT / "demo_app.py"), default_timeout=30).run()
    elapsed = time.perf_counter() - started
    assert not at.exception
    assert at.info[0].value == SAMPLE_BANNER  # "Sample data" on the page
    assert at.subheader[0].value == "Team status as of 09:42"
    table = at.dataframe[0].value
    assert list(table["Team"]) == ["Alpha", "Beta", "Delta", "Gamma"]
    assert list(table["Colour"]) == ["🔴 Red", "🟠 Amber", "🟠 Amber", "🟢 Green"]
    assert elapsed < 3  # AC43 (the manual check on a laptop is in the release checklist)


def test_demo_refresh_keeps_working():
    at = AppTest.from_file(str(ROOT / "demo_app.py"), default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception and at.subheader[0].value == "Team status as of 09:42"


def test_page_stops_with_the_settings_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # No config.yaml here
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert "settings file config.yaml was not found" in at.error[0].value
    assert not at.dataframe


def test_details_on_the_page():
    def page():
        from app import show_details
        from status_report.run import load_settings, make_client, read_portfolio

        portfolio = read_portfolio(make_client(True), load_settings(demo=True), demo=True)
        show_details(next(r for r in portfolio.rows if r.name == "Beta"))

    at = AppTest.from_function(page, default_timeout=30).run()
    assert not at.exception
    assert at.subheader[0].value == "Beta – 🟠 Amber"
    keys = list(at.dataframe[0].value["Key"])
    assert keys == ["BET-121", "BET-120", "BET-122"]  # Black, Red, Amber


@pytest.mark.parametrize("path", ["app.py", "demo_app.py"])
def test_page_files_exist(path):
    assert (ROOT / path).is_file()
