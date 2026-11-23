"""Reads tickets from Jira Cloud (SRG-13, D19, D23, D25; v2 plan S3).

The client sends GET requests only, so it cannot change Jira data (D25, spec N5).
v2 reads, for each team: the project, its active sprints (Agile API: board -> active
sprints), its next release (fix version), the tickets, and the first closed ticket.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta

import requests

from status_report.models import Release, Sprint, StatusChange, TeamData, Ticket

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
    "resolution",
]
CLEANED_UP = {"won't do", "duplicate"}  # Spec §4: cleaned up; never done, open or counted


NO_TOKEN = "No Jira token found. Add JIRA_API_TOKEN to .env."
BAD_TOKEN = "Jira did not accept the token. Make a new token and update .env."


class JiraError(Exception):
    """A Jira problem. The message never contains the token."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status  # HTTP status code, if Jira sent one


class ProjectNotFound(JiraError):
    """Jira does not know the project key in the settings file."""

    def __init__(self, project_key: str):
        super().__init__(
            f"Project {project_key} not found in Jira. Check the key in settings.", status=404
        )
        self.project_key = project_key


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str, session=None, sleep=time.sleep):
        self.site_url = base_url.rstrip("/")
        self.api_url = self.site_url
        self.browse_url: str | None = f"{self.site_url}/browse/"  # None: no ticket links
        self._auth = (email, token)
        self._session = session or requests.Session()
        self._sleep = sleep
        self._status_categories: dict[str, str] | None = None
        self._flag_field: str | None = None
        self._sprint_field: str | None = None
        self._fields_found = False
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
        if "JIRA_API_TOKEN" in missing:  # SRG-R13.3, AC27
            others = [name for name in missing if name != "JIRA_API_TOKEN"]
            also = f" Also add {', '.join(others)}." if others else ""
            raise JiraError(NO_TOKEN + also)
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
            if error.status != 401:
                raise
            cloud_id = self._cloud_id()
            self.api_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
            me = self._get("/rest/api/3/myself")
        self._connected = True
        return me.get("displayName", "unknown user")

    def check_project(self, project_key: str) -> None:
        """Stop if Jira does not know the project (SRG-R13.2, AC26)."""
        try:
            self._get(f"/rest/api/3/project/{project_key}")
        except JiraError as error:
            if error.status == 404:
                raise ProjectNotFound(project_key) from None
            raise

    # --- v2 reading: one team -------------------------------------------

    def prepare(self, need_flag: bool = False) -> None:
        """Read the shared lists once, before the parallel team reads (plan SD3)."""
        if not self._connected:
            self.connect()
        self._status_category_map()
        self._find_fields()
        if not need_flag:
            self._flag_field = None

    def read_team(
        self,
        project_key: str,
        work_types: tuple[str, ...],
        today: date,
        read_at: datetime,
        lookback_days: int,
        need_flag: bool = False,
        need_first_closed: bool = True,
    ) -> TeamData:
        """Read one team: open tickets, tickets changed in the last lookback_days, sprints,
        the next release and (for the forecast) the first closed ticket.

        The query is one day wider than the window, because Jira uses the time zone of the
        user profile. The rules filter the tickets exactly (status_report.metrics).
        """
        self.prepare(need_flag)
        self.check_project(project_key)
        sprints = self.active_sprints(project_key)
        release = self.next_release(project_key, today)
        types = ", ".join(f'"{name}"' for name in work_types)
        since = today - timedelta(days=lookback_days + 1)
        in_sprint = " OR sprint in openSprints()" if self._sprint_field else ""
        jql = (
            f'project = "{project_key}" AND issuetype in ({types}) '
            f'AND (statusCategory != Done OR updated >= "{since:%Y-%m-%d}"{in_sprint}) '
            "ORDER BY key"
        )
        fields = TICKET_FIELDS + [f for f in (self._flag_field, self._sprint_field) if f]
        categories = self._status_category_map()
        tickets = tuple(self._to_ticket(raw, categories) for raw in self._search(jql, fields))
        first = self.first_closed(project_key, work_types) if need_first_closed else None
        return TeamData(
            key=project_key,
            tickets=tickets,
            active_sprints=sprints,
            next_release=release,
            first_closed=first,
            read_at=read_at,
            browse_url=self.browse_url,
        )

    def active_sprints(self, project_key: str) -> tuple[Sprint, ...]:
        """Active sprints on the boards of the project. A board without sprints (Kanban) has none.

        A board can also show sprints of other projects; those are left out when Jira says
        which board a sprint belongs to (originBoardId).
        """
        boards = self._paged("/rest/agile/1.0/board", {"projectKeyOrId": project_key})
        board_ids = {board["id"] for board in boards}
        found: dict[int, Sprint] = {}
        for board_id in sorted(board_ids):
            try:
                sprints = self._paged(f"/rest/agile/1.0/board/{board_id}/sprint", {"state": "active"})
            except JiraError as error:
                if error.status == 400:  # "The board does not support sprints"
                    continue
                raise
            for raw in sprints:
                origin = raw.get("originBoardId")
                if origin is not None and origin not in board_ids:
                    continue
                sprint = _to_sprint(raw)
                if sprint.state == "active":
                    found[sprint.id] = sprint
        return tuple(found[key] for key in sorted(found))

    def _paged(self, path: str, params: dict) -> list[dict]:
        """All values of an Agile API list (startAt / isLast paging)."""
        values, start = [], 0
        while True:
            page = self._get(path, {**params, "startAt": start, "maxResults": 50})
            batch = page.get("values", [])
            values.extend(batch)
            start += len(batch)
            if page.get("isLast", True) or not batch:
                return values

    def next_release(self, project_key: str, today: date) -> Release | None:
        """Spec R4.2: the unreleased fix version with the earliest release date on or after today."""
        versions = self._get(f"/rest/api/3/project/{project_key}/versions")
        dated = [
            Release(v["name"], date.fromisoformat(v["releaseDate"]))
            for v in versions
            if not v.get("released") and not v.get("archived") and v.get("releaseDate")
        ]
        coming = [r for r in dated if r.release_date >= today]
        return min(coming, key=lambda r: (r.release_date, r.name)) if coming else None

    def first_closed(self, project_key: str, work_types: tuple[str, ...]) -> datetime | None:
        """Time of the first closed ticket that is not cleaned up (spec R4.3), from the
        Resolved date. None if the project has none."""
        types = ", ".join(f'"{name}"' for name in work_types)
        jql = (
            f'project = "{project_key}" AND issuetype in ({types}) AND statusCategory = Done '
            "ORDER BY resolutiondate ASC"
        )
        for raw in self._search(jql, ["resolution", "resolutiondate"], changelog=False):
            f = raw["fields"]
            if _resolution(f) in CLEANED_UP or not f.get("resolutiondate"):
                continue
            return _parse_datetime(f["resolutiondate"])
        return None

    # --- v1 reading: one week -------------------------------------------

    def fetch_tickets(
        self,
        project_key: str,
        work_types: tuple[str, ...],
        start: date,
        end: date,
        need_flag: bool = False,
    ) -> list[Ticket]:
        """Return the tickets that can matter for the week.

        The query is one day wider on each side, because Jira uses the time zone of the
        user profile. The weekly numbers do the exact date filtering in the time zone
        from config.yaml (status_report.metrics).
        """
        if not self._connected:
            self.connect()
        if need_flag:
            self._flag_field = self._find_flag_field()
        categories = self._status_category_map()

        types = ", ".join(f'"{name}"' for name in work_types)
        jql = (
            f'project = "{project_key}" AND issuetype in ({types}) '
            f'AND created < "{end + timedelta(days=2):%Y-%m-%d}" '
            f'AND (statusCategory != Done OR updated >= "{start - timedelta(days=1):%Y-%m-%d}") '
            "ORDER BY key"
        )
        fields = TICKET_FIELDS + ([self._flag_field] if self._flag_field else [])

        return [self._to_ticket(raw, categories) for raw in self._search(jql, fields)]

    def _search(self, jql: str, fields: list[str], changelog: bool = True):
        token = None
        while True:
            params = {"jql": jql, "fields": ",".join(fields), "maxResults": PAGE_SIZE}
            if changelog:
                params["expand"] = "changelog"
            if token:
                params["nextPageToken"] = token
            page = self._get("/rest/api/3/search/jql", params)
            for issue in page.get("issues", []):
                log = issue.get("changelog") or {}
                if changelog and log.get("total", 0) > len(log.get("histories", [])):
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
        self._find_fields()
        return self._flag_field

    def _find_fields(self) -> None:
        """The ids of the Flagged and Sprint fields (custom fields; the id differs per site)."""
        if self._fields_found:
            return
        for item in self._get("/rest/api/3/field"):
            if item.get("name") == "Flagged" and self._flag_field is None:
                self._flag_field = item["id"]
            if item.get("name") == "Sprint" and self._sprint_field is None:
                self._sprint_field = item["id"]
        self._fields_found = True

    def _cloud_id(self) -> str:
        try:
            response = self._session.get(
                f"{self.site_url}/_edge/tenant_info", timeout=TIMEOUT_SECONDS
            )
            cloud_id = response.json().get("cloudId") if response.status_code == 200 else None
        except (requests.RequestException, ValueError, AttributeError):
            cloud_id = None
        if not cloud_id:
            raise JiraError(BAD_TOKEN, status=401)
        return cloud_id

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
            resolution=(f.get("resolution") or {}).get("name"),
            sprints=tuple(_to_sprint(raw) for raw in (f.get(self._sprint_field) or ())
                          if isinstance(raw, dict)) if self._sprint_field else (),
        )

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
                raise JiraError(BAD_TOKEN, status=401)  # SRG-R13.3, AC28
            if response.status_code == 403:
                raise JiraError(
                    "Jira refused access (403). The token needs the scopes "
                    "read:jira-work and read:jira-user, and for sprints "
                    "read:board-scope:jira-software and read:sprint:jira-software.",
                    status=403,
                )
            if response.status_code >= 400:
                raise JiraError(
                    f"Jira error {response.status_code} on {path}.", status=response.status_code
                )
            return response.json()
        raise JiraError(f"Jira is busy or unavailable after {MAX_TRIES} tries ({path}).")


def _to_sprint(raw: dict) -> Sprint:
    return Sprint(
        id=int(raw["id"]),
        name=raw.get("name") or "",
        state=(raw.get("state") or "").lower(),
        end=_parse_datetime(raw.get("endDate")),
    )


def _resolution(fields: dict) -> str:
    name = (fields.get("resolution") or {}).get("name") or ""
    return name.replace("\u2019", "'").strip().lower()


def _retry_after(response) -> float | None:
    value = response.headers.get("Retry-After")
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime | None:
    """Jira dates: "2026-10-20T09:00:00.000+0000"; sprint dates: "2026-10-20T09:00:00.000Z"."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        return datetime.fromisoformat(value)
