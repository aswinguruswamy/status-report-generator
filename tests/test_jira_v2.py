"""v2 Jira reads: active sprints, next release, first closed ticket, parallel team reads,
and the recorded demo data (plan S3; spec SRG-R1.3, SRG-R2, SRG-R4.2, SRG-R14.1, N3, N4.1)."""

from __future__ import annotations

import importlib.util
import threading
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from test_jira_client import STATUSES, FakeResponse, FakeSession

from status_report.config import Config, Team, load_config
from status_report.demo import CONFIG_FILE, DATA_FILE, DemoSession, demo_client, demo_now
from status_report.jira_client import JiraClient, JiraError, ProjectNotFound
from status_report.models import Release, Sprint
from status_report.sources import MAX_PARALLEL_READS, read_teams

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://example.atlassian.net"
TODAY = date(2026, 12, 1)
READ_AT = datetime(2026, 12, 1, 14, 42, tzinfo=UTC)
FIELDS = [{"id": "customfield_10020", "name": "Sprint"}, {"id": "customfield_10021", "name": "Flagged"}]


def raw_sprint(sid, state, end="2026-12-08T22:00:00.000Z"):
    return {"id": sid, "name": f"Sprint {sid}", "state": state, "endDate": end}


def raw_issue(key, status="To Do", category="To Do", resolution=None, resolved=None, sprints=None):
    return {"key": key, "fields": {
        "summary": f"Title {key}", "issuetype": {"name": "Story"},
        "status": {"name": status, "statusCategory": {"name": category}},
        "priority": {"name": "High"}, "assignee": None, "duedate": None,
        "created": "2026-11-20T09:00:00.000+0000", "resolutiondate": resolved, "labels": [],
        "resolution": {"name": resolution} if resolution else None,
        "customfield_10020": sprints,
    }, "changelog": {"total": 0, "histories": []}}


def jira(project="ALP", boards=None, sprints=None, versions=None, issues=None, done_sorted=None,
         fail=None):
    """A fake Jira for one or more projects. `fail`: project keys that answer 500."""
    boards = boards if boards is not None else [{"id": 1}, {"id": 2}]
    sprints = sprints if sprints is not None else {
        1: [raw_sprint(11, "active"), raw_sprint(12, "active")],
        2: [raw_sprint(12, "active")],  # The same sprint on a second board: counted once
    }
    versions = versions if versions is not None else []
    issues = issues if issues is not None else [raw_issue(f"{project}-1")]
    done_sorted = done_sorted if done_sorted is not None else []
    fail = fail or set()

    def handler(url, params):
        path = url.replace(SITE, "")
        if path == "/rest/api/3/myself":
            return FakeResponse(data={"displayName": "Aswin"})
        if path == "/rest/api/3/status":
            return FakeResponse(data=STATUSES)
        if path == "/rest/api/3/field":
            return FakeResponse(data=FIELDS)
        if path.startswith("/rest/api/3/project/"):
            key = path.split("/")[5]
            if key in fail:
                return FakeResponse(status_code=500)
            if key == "XYZ":
                return FakeResponse(status_code=404)
            return FakeResponse(data=versions if path.endswith("/versions") else {"key": key})
        if path == "/rest/agile/1.0/board":
            return FakeResponse(data={"values": boards, "isLast": True})
        if path.startswith("/rest/agile/1.0/board/"):
            board = int(path.split("/")[5])
            if board not in sprints:
                return FakeResponse(status_code=400)  # Kanban: no sprints
            return FakeResponse(data={"values": sprints[board], "isLast": True})
        if path == "/rest/api/3/search/jql":
            if "ORDER BY resolutiondate ASC" in params["jql"]:
                return FakeResponse(data={"issues": done_sorted, "isLast": True})
            return FakeResponse(data={"issues": issues, "isLast": True})
        raise AssertionError(f"unexpected call {path}")

    return handler


def client_for(handler):
    session = FakeSession(handler)
    return JiraClient(SITE, "a@b.com", "token", session=session, sleep=lambda s: None), session


def read(client, key="ALP", first=True):
    return client.read_team(key, ("Story", "Task", "Bug"), TODAY, READ_AT, 84,
                            need_first_closed=first)


def test_active_sprints_from_all_boards_counted_once():
    client, _ = client_for(jira())
    data = read(client)
    assert [s.id for s in data.active_sprints] == [11, 12]
    assert data.active_sprints[0] == Sprint(11, "Sprint 11", "active",
                                            datetime(2026, 12, 8, 22, tzinfo=UTC))


def test_board_without_sprints_gives_no_active_sprint():
    client, _ = client_for(jira(boards=[{"id": 3}], sprints={}))
    assert read(client).active_sprints == ()


def test_other_board_errors_are_not_hidden():
    def handler(url, params):
        if "/board/1/sprint" in url:
            return FakeResponse(status_code=403)
        return jira()(url, params)

    client, _ = client_for(handler)
    with pytest.raises(JiraError, match="403"):
        read(client)


def test_next_release_is_the_earliest_unreleased_on_or_after_today():
    versions = [
        {"name": "1.0", "released": True, "releaseDate": "2026-12-05"},
        {"name": "old", "released": False, "releaseDate": "2026-11-30"},  # Before today
        {"name": "no date", "released": False},
        {"name": "archived", "released": False, "archived": True, "releaseDate": "2026-12-02"},
        {"name": "2.0", "released": False, "releaseDate": "2027-01-20"},
        {"name": "1.5", "released": False, "releaseDate": "2026-12-15"},
    ]
    client, _ = client_for(jira(versions=versions))
    assert read(client).next_release == Release("1.5", date(2026, 12, 15))


def test_release_dated_today_counts():
    versions = [{"name": "today", "released": False, "releaseDate": "2026-12-01"}]
    client, _ = client_for(jira(versions=versions))
    assert read(client).next_release == Release("today", TODAY)


def test_no_dated_unreleased_version_gives_no_release():
    client, _ = client_for(jira(versions=[{"name": "Next", "released": False}]))
    assert read(client).next_release is None


def test_first_closed_skips_cleaned_up_tickets():
    done = [
        raw_issue("ALP-1", "Done", "Done", "Won't Do", "2026-01-02T10:00:00.000+0000"),
        raw_issue("ALP-2", "Done", "Done", "Duplicate", "2026-01-03T10:00:00.000+0000"),
        raw_issue("ALP-3", "Done", "Done", "Done", "2026-02-10T10:00:00.000+0000"),
    ]
    client, _ = client_for(jira(done_sorted=done))
    assert read(client).first_closed == datetime(2026, 2, 10, 10, tzinfo=UTC)


def test_first_closed_is_none_without_closed_tickets_or_when_not_needed():
    client, session = client_for(jira())
    assert read(client).first_closed is None
    assert read(client, first=False).first_closed is None
    searches = [c for c in session.calls if c[1].endswith("/search/jql")]
    assert sum("resolutiondate ASC" in c[2]["jql"] for c in searches) == 1


def test_ticket_has_resolution_and_sprints():
    issues = [raw_issue("ALP-1", "Done", "Done", "Won't Do", "2026-11-28T10:00:00.000+0000",
                        sprints=[raw_sprint(11, "active"), raw_sprint(9, "closed")])]
    client, _ = client_for(jira(issues=issues))
    ticket = read(client).tickets[0]
    assert ticket.resolution == "Won't Do"
    assert [(s.id, s.state) for s in ticket.sprints] == [(11, "active"), (9, "closed")]


def test_query_reads_open_tickets_recent_changes_and_sprint_tickets():
    client, session = client_for(jira())
    read(client)
    jql = next(c[2]["jql"] for c in session.calls
               if c[1].endswith("/search/jql") and "ORDER BY key" in c[2]["jql"])
    assert 'project = "ALP"' in jql and 'issuetype in ("Story", "Task", "Bug")' in jql
    assert 'statusCategory != Done OR updated >= "2026-09-07"' in jql  # 84 + 1 days back
    assert "sprint in openSprints()" in jql
    assert all(method == "GET" for method, _, _ in session.calls)


def test_unknown_project_raises_project_not_found():
    client, _ = client_for(jira())
    with pytest.raises(ProjectNotFound, match="Project XYZ not found in Jira"):
        read(client, "XYZ")


def test_browse_link_points_to_the_site():
    client, _ = client_for(jira())
    assert read(client).browse_url == f"{SITE}/browse/"


# --- Parallel reads (plan SD3, spec N3, N4.1) --------------------------------------


def config_for(*keys, forecast=True):
    return Config(teams=tuple(Team(k, k.title()) for k in keys), timezone="UTC", forecast=forecast)


def test_one_failed_team_does_not_stop_the_others():
    client, _ = client_for(jira(fail={"BET"}))
    result = read_teams(client, config_for("ALP", "BET", "GAM"), READ_AT)
    assert list(result) == ["ALP", "BET", "GAM"]
    assert isinstance(result["BET"], JiraError)
    assert result["ALP"].key == "ALP" and result["GAM"].key == "GAM"


def test_bad_token_stops_the_whole_read():
    client, _ = client_for(lambda url, params: FakeResponse(status_code=401) if "tenant" not in url
                           else FakeResponse(status_code=404))
    with pytest.raises(JiraError, match="did not accept the token"):
        read_teams(client, config_for("ALP"), READ_AT)


def test_reads_run_in_parallel_but_at_most_4_at_a_time():
    active, peak, lock = [0], [0], threading.Lock()
    base = jira()

    def slow(url, params):
        if url.endswith("/versions"):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.05)
            with lock:
                active[0] -= 1
        return base(url, params)

    client, _ = client_for(slow)
    keys = [f"T{n}" for n in range(10)]
    started = time.perf_counter()
    result = read_teams(client, config_for(*keys), READ_AT)
    elapsed = time.perf_counter() - started
    assert len(result) == 10 and not any(isinstance(v, Exception) for v in result.values())
    assert peak[0] == MAX_PARALLEL_READS == 4
    assert elapsed < 10 * 0.05  # Faster than one team after the other


def test_forecast_off_reads_14_days_and_no_first_closed():
    client, session = client_for(jira())
    read_teams(client, config_for("ALP", forecast=False), READ_AT)
    jqls = [c[2]["jql"] for c in session.calls if c[1].endswith("/search/jql")]
    assert len(jqls) == 1 and 'updated >= "2026-11-16"' in jqls[0]


# --- Demo data (plan SD2, spec SRG-R14.1) -------------------------------------------


def test_demo_reads_4_teams_with_the_real_client_and_no_token(monkeypatch):
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    config = load_config(CONFIG_FILE)
    result = read_teams(demo_client(), config, demo_now())
    assert [t.name for t in config.teams] == ["Alpha", "Beta", "Gamma", "Delta"]
    assert all(not isinstance(v, Exception) for v in result.values())
    assert [s.name for s in result["BET"].active_sprints] == ["BET Web 10", "BET Mobile 1"]
    assert result["GAM"].active_sprints == ()  # Kanban board
    assert result["ALP"].next_release == Release("2.4", date(2026, 12, 15))
    assert result["GAM"].next_release is None
    assert all(v.browse_url is None for v in result.values())  # No links for sample data
    # 12 weeks of history, except the young team Delta
    for key in ("ALP", "BET", "GAM"):
        assert (demo_now() - result[key].first_closed).days >= 84
    assert (demo_now() - result["DEL"].first_closed).days < 83


def test_demo_session_answers_unknown_requests_with_404():
    client = JiraClient("https://demo.invalid", "x", "y", session=DemoSession())
    with pytest.raises(ProjectNotFound):
        client.check_project("XYZ")


def test_demo_data_matches_the_script():
    spec = importlib.util.spec_from_file_location("make_demo", ROOT / "scripts" / "make_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert DATA_FILE.read_text(encoding="utf-8") == module.text(), (
        "demo/jira.json is old. Run: python scripts/make_demo.py"
    )


def test_demo_data_is_made_up():
    import re

    text = DATA_FILE.read_text(encoding="utf-8")
    assert "atlassian.net" not in text and "SRG-" not in text
    assert not re.search(r"[\w.]+@[\w-]+\.\w+", text)  # No email address
