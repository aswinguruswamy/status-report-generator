"""Tests for the Jira client with fake Jira answers (SRG-13)."""

from datetime import UTC, date, datetime

import pytest

from status_report.jira_client import JiraClient, JiraError

TOKEN = "fake-token-value-123"
SITE = "https://example.atlassian.net"
STATUSES = [
    {"name": "To Do", "statusCategory": {"name": "To Do"}},
    {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
    {"name": "Review", "statusCategory": {"name": "In Progress"}},
    {"name": "Done", "statusCategory": {"name": "Done"}},
]


class FakeResponse:
    def __init__(self, status_code=200, data=None, headers=None):
        self.status_code = status_code
        self._data = data
        self.headers = headers or {}

    def json(self):
        return self._data


class FakeSession:
    """Answers GET requests from a list of rules. Records each call."""

    def __init__(self, handler):
        self.handler = handler
        self.calls = []

    def get(self, url, params=None, auth=None, timeout=None):
        self.calls.append(("GET", url, params))
        return self.handler(url, params or {})

    def __getattr__(self, name):  # post, put, delete, patch...
        raise AssertionError(f"The client used '{name}'. Only GET is allowed (D25).")


def issue(key, status="To Do", category="To Do", created="2026-10-20T09:00:00.000+0000",
          histories=None, resolved=None, priority="High", flagged=None):
    fields = {
        "summary": f"Title {key}",
        "issuetype": {"name": "Story"},
        "status": {"name": status, "statusCategory": {"name": category}},
        "priority": {"name": priority} if priority else None,
        "assignee": {"displayName": "Person A"},
        "duedate": "2026-10-24",
        "created": created,
        "resolutiondate": resolved,
        "labels": ["blocked"],
        "description": "SECRET DESCRIPTION",
    }
    if flagged is not None:
        fields["customfield_10021"] = flagged
    histories = histories or []
    return {"key": key, "fields": fields,
            "changelog": {"total": len(histories), "histories": histories}}


def move(at, from_status, to_status):
    return {"created": at, "items": [{"field": "status", "fromString": from_status,
                                      "toString": to_status}]}


def handler_for(issues, page_size=100, extra=None):
    def handler(url, params):
        if extra:
            answer = extra(url, params)
            if answer is not None:
                return answer
        if url.endswith("/rest/api/3/myself"):
            return FakeResponse(data={"displayName": "Aswin"})
        if url.endswith("/rest/api/3/status"):
            return FakeResponse(data=STATUSES)
        if url.endswith("/rest/api/3/field"):
            return FakeResponse(data=[{"id": "customfield_10021", "name": "Flagged"}])
        if url.endswith("/rest/api/3/search/jql"):
            start = int(params.get("nextPageToken") or 0)
            page = issues[start:start + page_size]
            nxt = start + page_size
            data = {"issues": page}
            if nxt < len(issues):
                data["nextPageToken"] = str(nxt)
            else:
                data["isLast"] = True
            return FakeResponse(data=data)
        raise AssertionError(f"unexpected URL {url}")
    return handler


def client_with(handler):
    session = FakeSession(handler)
    return JiraClient(SITE, "a@b.com", TOKEN, session=session, sleep=lambda s: None), session


WEEK = (date(2026, 10, 19), date(2026, 10, 25))


def fetch(client, need_flag=False):
    return client.fetch_tickets("SRG", ("Story", "Task", "Bug"), *WEEK, need_flag=need_flag)


# --- AC: read only (D25) ---------------------------------------------------

def test_client_sends_get_requests_only():
    client, session = client_with(handler_for([issue("SRG-1")]))
    fetch(client)
    assert session.calls and all(call[0] == "GET" for call in session.calls)


# --- AC: all pages, more than 100 tickets -----------------------------------

def test_reads_all_pages_of_more_than_100_tickets():
    issues = [issue(f"SRG-{n}") for n in range(1, 251)]
    client, session = client_with(handler_for(issues))
    tickets = fetch(client)
    assert len(tickets) == 250
    searches = [c for c in session.calls if c[1].endswith("/search/jql")]
    assert len(searches) == 3


def test_query_uses_project_and_work_types():
    client, session = client_with(handler_for([]))
    fetch(client)
    jql = next(c for c in session.calls if c[1].endswith("/search/jql"))[2]["jql"]
    assert 'project = "SRG"' in jql
    assert 'issuetype in ("Story", "Task", "Bug")' in jql


# --- AC: only the allowed fields, one common Ticket object ------------------

def test_ticket_has_the_allowed_fields_and_no_description():
    client, session = client_with(handler_for([issue("SRG-1")]))
    ticket = fetch(client)[0]
    assert ticket.key == "SRG-1"
    assert ticket.title == "Title SRG-1"
    assert ticket.work_type == "Story"
    assert ticket.priority == "High"
    assert ticket.assignee == "Person A"
    assert ticket.due_date == date(2026, 10, 24)
    assert ticket.labels == ("blocked",)
    assert not hasattr(ticket, "description")
    fields = next(c for c in session.calls if c[1].endswith("/search/jql"))[2]["fields"]
    assert "description" not in fields and "comment" not in fields


def test_ticket_without_priority():
    client, _ = client_with(handler_for([issue("SRG-1", priority=None)]))
    assert fetch(client)[0].priority is None


# --- D19: done date from the status history ---------------------------------

def test_done_date_is_the_last_move_into_a_done_status():
    histories = [
        move("2026-10-20T10:00:00.000+0000", "To Do", "In Progress"),
        move("2026-10-21T10:00:00.000+0000", "In Progress", "Done"),
        move("2026-10-22T10:00:00.000+0000", "Done", "In Progress"),
        move("2026-10-23T15:00:00.000+0000", "In Progress", "Done"),
    ]
    raw = issue("SRG-1", "Done", "Done", histories=histories,
                resolved="2026-10-21T10:00:00.000+0000")
    client, _ = client_with(handler_for([raw]))
    ticket = fetch(client)[0]
    assert ticket.done_date == datetime(2026, 10, 23, 15, tzinfo=UTC)
    assert len(ticket.history) == 4


def test_resolved_date_is_the_second_check_when_no_history():
    raw = issue("SRG-1", "Done", "Done", resolved="2026-10-22T08:00:00.000+0000")
    client, _ = client_with(handler_for([raw]))
    assert fetch(client)[0].done_date == datetime(2026, 10, 22, 8, tzinfo=UTC)


def test_query_is_one_day_wider_than_the_week():
    # The exact filter is in metrics, in the time zone from config.yaml (SRG-33, C3).
    client, session = client_with(handler_for([]))
    fetch(client)
    jql = next(c for c in session.calls if c[1].endswith("/search/jql"))[2]["jql"]
    assert 'created < "2026-10-27"' in jql
    assert 'updated >= "2026-10-18"' in jql


def test_client_does_not_drop_a_ticket_at_the_week_limit():
    # Sunday 23:30 in Toronto is Monday 03:30 in UTC.
    raw = issue("SRG-1", created="2026-10-26T03:30:00.000+0000")
    client, _ = client_with(handler_for([raw]))
    assert [t.key for t in fetch(client)] == ["SRG-1"]


def test_long_history_is_read_in_full():
    raw = issue("SRG-1", "Done", "Done")
    raw["changelog"] = {"total": 150, "histories": []}

    def extra(url, params):
        if url.endswith("/issue/SRG-1/changelog"):
            return FakeResponse(data={"values": [
                move("2026-10-22T10:00:00.000+0000", "In Progress", "Done")], "isLast": True})
        return None

    client, _ = client_with(handler_for([raw], extra=extra))
    assert fetch(client)[0].done_date.day == 22


# --- Flag (needed for blocked_method: flag) ----------------------------------

def test_flag_is_read_when_needed():
    raw = issue("SRG-1", flagged=[{"value": "Impediment"}])
    client, _ = client_with(handler_for([raw]))
    assert fetch(client, need_flag=True)[0].flagged is True


# --- AC: wrong or missing token ---------------------------------------------

def test_wrong_token_gives_a_clear_message_without_the_token():
    def handler(url, params):
        if "tenant_info" in url:
            return FakeResponse(data={"cloudId": "abc"})
        return FakeResponse(status_code=401)

    client, _ = client_with(handler)
    with pytest.raises(JiraError) as error:
        client.connect()
    assert error.value.status == 401
    assert "401" in str(error.value)
    assert TOKEN not in str(error.value)


def test_missing_token_in_env(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("JIRA_BASE_URL", SITE)
    monkeypatch.setenv("JIRA_EMAIL", "a@b.com")
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    with pytest.raises(JiraError, match="Missing in .env: JIRA_API_TOKEN"):
        JiraClient.from_env()


def test_scoped_token_changes_to_the_api_gateway():
    def handler(url, params):
        if "tenant_info" in url:
            return FakeResponse(data={"cloudId": "cloud-123"})
        if url.startswith(SITE):
            return FakeResponse(status_code=401)
        return handler_for([])(url, params)

    client, _ = client_with(handler)
    assert client.connect() == "Aswin"
    assert client.api_url == "https://api.atlassian.com/ex/jira/cloud-123"


# --- AC: rate limit -----------------------------------------------------------

def test_rate_limit_waits_and_tries_again():
    answers = iter([FakeResponse(429, headers={"Retry-After": "3"}),
                    FakeResponse(data={"displayName": "Aswin"})])
    waits = []
    session = FakeSession(lambda url, params: next(answers))
    client = JiraClient(SITE, "a@b.com", TOKEN, session=session, sleep=waits.append)
    assert client.connect() == "Aswin"
    assert waits == [3.0]


def test_rate_limit_stops_after_five_tries():
    session = FakeSession(lambda url, params: FakeResponse(429))
    client = JiraClient(SITE, "a@b.com", TOKEN, session=session, sleep=lambda s: None)
    with pytest.raises(JiraError, match="after 5 tries"):
        client.connect()


def test_403_does_not_change_to_the_gateway():
    def handler(url, params):
        if "tenant_info" in url:
            raise AssertionError("The client must not try the gateway for a 403.")
        return FakeResponse(status_code=403)

    client, _ = client_with(handler)
    with pytest.raises(JiraError) as error:
        client.connect()
    assert error.value.status == 403
