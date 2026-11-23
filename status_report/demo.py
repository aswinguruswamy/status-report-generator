"""Demo mode: recorded Jira answers for 4 made-up teams (spec SRG-R14.1; plan SD2).

The demo uses the real Jira client and the real rules. Only the network is replaced:
DemoSession answers each GET request from demo/jira.json. It needs no Jira account or token.
The data has a fixed read time (DEMO_NOW), so the demo shows the same result each time
(spec N2). Make the data again with: python scripts/make_demo.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DEMO_FOLDER = ROOT / "demo"
DATA_FILE = DEMO_FOLDER / "jira.json"
CONFIG_FILE = DEMO_FOLDER / "config.yaml"
SITE = "https://demo.invalid"  # Not a real site. Sample data has no ticket links (spec R11.3).
SAMPLE_DATA = "Sample data"  # Shown on the page and in the report (spec SRG-R14.2)


class DemoResponse:
    def __init__(self, status_code: int, data):
        self.status_code = status_code
        self._data = data
        self.headers: dict[str, str] = {}

    def json(self):
        return self._data


@cache
def load_data(path: Path = DATA_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def demo_now() -> datetime:
    """The fixed read time of the sample data."""
    return datetime.fromisoformat(load_data()["now"])


class DemoSession:
    """Answers the Jira client's GET requests from the recorded data. GET only (D25)."""

    def __init__(self, data: dict | None = None):
        self.data = data or load_data()
        self.calls: list[str] = []

    def get(self, url, params=None, auth=None, timeout=None):
        path = urlparse(url).path
        self.calls.append(path)
        params = params or {}
        projects = self.data["projects"]
        if path == "/rest/api/3/myself":
            return DemoResponse(200, {"displayName": "Sample user"})
        if path == "/rest/api/3/status":
            return DemoResponse(200, self.data["statuses"])
        if path == "/rest/api/3/field":
            return DemoResponse(200, self.data["fields"])
        match = re.fullmatch(r"/rest/api/3/project/([A-Z0-9_]+)(/versions)?", path)
        if match:
            project = projects.get(match.group(1))
            if project is None:
                return DemoResponse(404, {"errorMessages": ["No project could be found."]})
            if match.group(2):
                return DemoResponse(200, project["versions"])
            return DemoResponse(200, {"key": match.group(1), "name": project["name"]})
        if path == "/rest/agile/1.0/board":
            project = projects.get(params.get("projectKeyOrId"), {})
            boards = [{"id": board["id"], "type": board["type"]} for board in project.get("boards", [])]
            return DemoResponse(200, {"values": boards, "isLast": True})
        match = re.fullmatch(r"/rest/agile/1.0/board/(\d+)/sprint", path)
        if match:
            return self._sprints(int(match.group(1)), params.get("state"))
        if path == "/rest/api/3/search/jql":
            return DemoResponse(200, self._search(params.get("jql", "")))
        return DemoResponse(404, {"errorMessages": [f"No recorded answer for {path}."]})

    def _sprints(self, board_id: int, state: str | None):
        for project in self.data["projects"].values():
            for board in project.get("boards", []):
                if board["id"] == board_id:
                    if board["type"] != "scrum":
                        return DemoResponse(400, {"errorMessages": ["The board does not support sprints"]})
                    sprints = [s for s in board["sprints"] if state is None or s["state"] == state]
                    return DemoResponse(200, {"values": sprints, "isLast": True})
        return DemoResponse(404, {"errorMessages": ["Board not found."]})

    def _search(self, jql: str) -> dict:
        """Recorded issues of the project in the query. The client filters them exactly."""
        match = re.search(r'project = "([A-Z0-9_]+)"', jql)
        project = self.data["projects"].get(match.group(1)) if match else None
        issues = list(project["issues"]) if project else []
        since = re.search(r'updated >= "(\d{4}-\d{2}-\d{2})"', jql)
        if since:  # Open tickets, tickets changed since the date, and tickets in an active sprint
            issues = [i for i in issues if _open(i) or _updated(i) >= since.group(1) or _in_active_sprint(i)]
        if "statusCategory = Done ORDER BY resolutiondate ASC" in jql:
            issues = [i for i in issues if i["fields"]["status"]["statusCategory"]["name"] == "Done"]
            issues.sort(key=lambda i: i["fields"].get("resolutiondate") or "9999")
        return {"issues": issues, "isLast": True}


def _open(issue: dict) -> bool:
    return issue["fields"]["status"]["statusCategory"]["name"] != "Done"


def _updated(issue: dict) -> str:
    """Date of the last change, in the format of the query (YYYY-MM-DD)."""
    times = [issue["fields"]["created"]] + [h["created"] for h in issue["changelog"]["histories"]]
    return max(times)[:10]


def _in_active_sprint(issue: dict) -> bool:
    sprints = next((v for k, v in issue["fields"].items() if k.startswith("customfield") and
                    isinstance(v, list)), None) or []
    return any(s.get("state") == "active" for s in sprints)


def demo_client():
    """A Jira client that reads the recorded sample data."""
    from status_report.jira_client import JiraClient

    client = JiraClient(SITE, "sample@demo.invalid", "no-token", session=DemoSession())
    client.browse_url = None  # Sample tickets are not in Jira (spec SRG-R11.3)
    return client
