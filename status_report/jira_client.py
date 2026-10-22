"""Reads tickets from Jira Cloud (SRG-13, D19, D23, D25).

The client sends GET requests only, so it cannot change Jira data (D25).
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime

import requests

from status_report.models import StatusChange, Ticket

PAGE_SIZE = 100
MAX_TRIES = 5
TIMEOUT_SECONDS = 30
TICKET_FIELDS = [
    "summary",
    "issuetype",
    "status",
    "priority",
    "assignee",
    "duedate",
    "created",
    "resolutiondate",
    "labels",
]


class JiraError(Exception):
    """A Jira problem. The message never contains the token."""


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str, session=None, sleep=time.sleep):
        self.site_url = base_url.rstrip("/")
        self.api_url = self.site_url
        self._auth = (email, token)
        self._session = session or requests.Session()
        self._sleep = sleep
        self._status_categories: dict[str, str] | None = None
        self._flag_field: str | None = None
        self._connected = False

    # --- setup ---------------------------------------------------------

    @classmethod
    def from_env(cls, **kwargs) -> JiraClient:
        """Make a client from the values in .env."""
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        names = ["JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
        missing = [name for name in names if not os.environ.get(name, "").strip()]
        if missing:
            raise JiraError(
                f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and add the values."
            )
        return cls(*(os.environ[name].strip() for name in names), **kwargs)

    def connect(self) -> str:
        """Check the token. Return the display name of the account.

        A classic token works on the site address. A scoped token works only through
        api.atlassian.com, so the client changes to that address if the site refuses.
        """
        try:
            me = self._get("/rest/api/3/myself")
        except JiraError as error:
            if "401" not in str(error):
                raise
            cloud_id = self._cloud_id()
            self.api_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
            me = self._get("/rest/api/3/myself")
        self._connected = True
        return me.get("displayName", "unknown user")

    # --- reading -------------------------------------------------------

    def fetch_tickets(
        self,
        project_key: str,
        work_types: tuple[str, ...],
        start: date,
        end: date,
        need_flag: bool = False,
    ) -> list[Ticket]:
        """Return the tickets that were open in the week, or created or closed in it."""
        if not self._connected:
            self.connect()
        if need_flag:
            self._flag_field = self._find_flag_field()
        categories = self._status_category_map()

        types = ", ".join(f'"{name}"' for name in work_types)
        jql = (
            f'project = "{project_key}" AND issuetype in ({types}) '
            f'AND created <= "{end:%Y-%m-%d} 23:59" '
            f'AND (statusCategory != Done OR updated >= "{start:%Y-%m-%d}") '
            "ORDER BY key"
        )
        fields = TICKET_FIELDS + ([self._flag_field] if self._flag_field else [])

        tickets = []
        for raw in self._search(jql, fields):
            ticket = self._to_ticket(raw, categories)
            if self._in_week(ticket, start, end):
                tickets.append(ticket)
        return tickets

    def _search(self, jql: str, fields: list[str]):
        token = None
        while True:
            params = {
                "jql": jql,
                "fields": ",".join(fields),
                "expand": "changelog",
                "maxResults": PAGE_SIZE,
            }
            if token:
                params["nextPageToken"] = token
            page = self._get("/rest/api/3/search/jql", params)
            for issue in page.get("issues", []):
                changelog = issue.get("changelog") or {}
                if changelog.get("total", 0) > len(changelog.get("histories", [])):
                    issue["changelog"] = {"histories": self._full_changelog(issue["key"])}
                yield issue
            token = page.get("nextPageToken")
            if not token or page.get("isLast", False):
                return

    def _full_changelog(self, key: str) -> list[dict]:
        histories, start_at = [], 0
        while True:
            page = self._get(
                f"/rest/api/3/issue/{key}/changelog",
                {"startAt": start_at, "maxResults": PAGE_SIZE},
            )
            values = page.get("values", [])
            histories.extend(values)
            start_at += len(values)
            if page.get("isLast", True) or not values:
                return histories

    def _status_category_map(self) -> dict[str, str]:
        if self._status_categories is None:
            statuses = self._get("/rest/api/3/status")
            self._status_categories = {
                s["name"].lower(): s["statusCategory"]["name"] for s in statuses
            }
        return self._status_categories

    def _find_flag_field(self) -> str | None:
        for item in self._get("/rest/api/3/field"):
            if item.get("name") == "Flagged":
                return item["id"]
        return None

    def _cloud_id(self) -> str:
        response = self._session.get(
            f"{self.site_url}/_edge/tenant_info", timeout=TIMEOUT_SECONDS
        )
        if response.status_code != 200:
            raise JiraError(
                "Jira refused the token (401). Check JIRA_EMAIL and JIRA_API_TOKEN in .env."
            )
        return response.json()["cloudId"]

    # --- conversion ----------------------------------------------------

    def _to_ticket(self, raw: dict, categories: dict[str, str]) -> Ticket:
        f = raw["fields"]
        history = []
        for entry in (raw.get("changelog") or {}).get("histories", []):
            for item in entry.get("items", []):
                if item.get("field") == "status":
                    from_status = item.get("fromString")
                    to_status = item.get("toString") or ""
                    history.append(
                        StatusChange(
                            at=_parse_datetime(entry["created"]),
                            from_status=from_status,
                            to_status=to_status,
                            from_category=categories.get((from_status or "").lower()),
                            to_category=categories.get(to_status.lower()),
                        )
                    )
        history.sort(key=lambda change: change.at)

        status = f["status"]["name"]
        category = f["status"]["statusCategory"]["name"]
        resolved = _parse_datetime(f.get("resolutiondate"))
        done_date = None
        if category == "Done":
            moves = [c.at for c in history if c.to_category == "Done"]
            done_date = moves[-1] if moves else resolved  # D19: Resolved is the second check

        return Ticket(
            key=raw["key"],
            title=f.get("summary") or "",
            work_type=f["issuetype"]["name"],
            status=status,
            status_category=category,
            priority=(f.get("priority") or {}).get("name"),
            assignee=(f.get("assignee") or {}).get("displayName"),
            due_date=date.fromisoformat(f["duedate"]) if f.get("duedate") else None,
            created=_parse_datetime(f["created"]),
            done_date=done_date,
            resolved=resolved,
            labels=tuple(f.get("labels") or ()),
            flagged=bool(self._flag_field and f.get(self._flag_field)),
            history=tuple(history),
        )

    @staticmethod
    def _in_week(ticket: Ticket, start: date, end: date) -> bool:
        if ticket.created.date() > end:
            return False
        if ticket.done_date is None:
            return True
        return ticket.done_date.date() >= start

    # --- the only way to call Jira: GET ---------------------------------

    def _get(self, path: str, params: dict | None = None):
        url = f"{self.api_url}{path}"
        for attempt in range(1, MAX_TRIES + 1):
            try:
                response = self._session.get(
                    url, params=params, auth=self._auth, timeout=TIMEOUT_SECONDS
                )
            except requests.RequestException as error:
                raise JiraError(f"Cannot reach Jira at {self.site_url}: {type(error).__name__}.") from None

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_TRIES:
                    break
                wait = _retry_after(response) or 2**attempt
                self._sleep(wait)
                continue
            if response.status_code == 401:
                raise JiraError(
                    "Jira refused the token (401). Check JIRA_EMAIL and JIRA_API_TOKEN in .env."
                )
            if response.status_code == 403:
                raise JiraError(
                    "Jira refused access (403). The token needs the scopes "
                    "read:jira-work and read:jira-user."
                )
            if response.status_code >= 400:
                raise JiraError(f"Jira error {response.status_code} on {path}.")
            return response.json()
        raise JiraError(f"Jira is busy or unavailable after {MAX_TRIES} tries ({path}).")


def _retry_after(response) -> float | None:
    value = response.headers.get("Retry-After")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
