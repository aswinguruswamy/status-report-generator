"""Make the demo data in demo/jira.json: recorded Jira answers for 4 made-up teams (plan SD2).

Run it after a change to the demo teams:

    python scripts/make_demo.py

The data is made up. No real project, person or ticket is in it. A fixed seed makes the same
file each time, and a test checks that demo/jira.json matches this script.

The 4 teams show the main cases of the spec:
  Alpha (ALP) - Red: a P1 ticket is blocked. One sprint. Release planned 15 Dec, forecast later.
  Beta  (BET) - Amber: other tickets blocked and overdue. 2 active sprints. Unknown priority.
  Gamma (GAM) - Green: Kanban board, no sprint ("last 14 days"). Release without a date.
  Delta (DEL) - Amber: closed fewer than opened. Young team: not enough history for a forecast.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "demo" / "jira.json"
SEED = 2026
ZONE = timezone(timedelta(hours=-5))  # America/Toronto in December (EST)
NOW = datetime(2026, 12, 1, 9, 42, tzinfo=ZONE)
TODAY = NOW.date()
SPRINT_FIELD, FLAG_FIELD = "customfield_10020", "customfield_10021"
CATEGORY = {"To Do": "To Do", "In Progress": "In Progress", "Blocked": "In Progress",
            "In Review": "In Progress", "Done": "Done"}
PEOPLE = ["Priya N", "Tom R", "Lena K", "Sam O", "Ana M", "Jon P", None]
WORDS = ["login page", "order export", "search filter", "invoice PDF", "mobile menu",
         "price rules", "email template", "audit log", "user roles", "report page",
         "payment form", "date picker", "help text", "data import", "status badge",
         "settings page", "error message", "cache layer", "API limits", "sign-up flow"]
VERBS = ["Fix", "Add", "Update", "Speed up", "Test", "Clean up", "Show", "Check"]


def day(offset: int, hour: int = 10) -> datetime:
    return datetime.combine(TODAY + timedelta(days=offset), time(hour), ZONE)


def ts(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000%z")


def sprint_ts(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def sprint(sid: int, name: str, start: int, length: int = 14, board: int = 1) -> dict:
    end = start + length
    state = "closed" if end <= 0 else ("active" if start <= 0 else "future")
    return {"id": sid, "name": name, "state": state, "boardId": board,
            "startDate": sprint_ts(day(start, 9)), "endDate": sprint_ts(day(end, 17))}


class Team:
    def __init__(self, key: str, name: str, rng: random.Random):
        self.key, self.name, self.rng = key, name, rng
        self.issues: list[dict] = []
        self.number = 0

    def issue(self, *, created: int, moves=(), priority="Medium", due: int | None = None,
              sprints=(), resolution: str | None = None, work_type="Story", title=None,
              labels=()) -> str:
        """Add one issue. moves: (day offset, new status); the first status is To Do."""
        self.number += 1
        key = f"{self.key}-{self.number}"
        status, histories = "To Do", []
        for number, (offset, new) in enumerate(moves):
            hour = 11 + number % 5
            histories.append({"id": f"{self.number}{number}", "created": ts(day(offset, hour)),
                              "items": [{"field": "status", "fromString": status, "toString": new}]})
            status = new
        done = [h["created"] for h in histories if h["items"][0]["toString"] == "Done"]
        if CATEGORY[status] == "Done" and resolution is None:
            resolution = "Done"
        fields = {
            "summary": title or f"{self.rng.choice(VERBS)} the {self.rng.choice(WORDS)}",
            "issuetype": {"name": work_type},
            "status": {"name": status, "statusCategory": {"name": CATEGORY[status]}},
            "priority": {"name": priority} if priority else None,
            "assignee": ({"displayName": p} if (p := self.rng.choice(PEOPLE)) else None),
            "duedate": (TODAY + timedelta(days=due)).isoformat() if due is not None else None,
            "created": ts(day(created, 9)),
            "resolutiondate": done[-1] if done and CATEGORY[status] == "Done" else None,
            "labels": list(labels),
            "resolution": {"name": resolution} if resolution else None,
            SPRINT_FIELD: list(sprints) or None,
            FLAG_FIELD: None,
        }
        self.issues.append({"key": key, "fields": fields, "changelog": {
            "startAt": 0, "maxResults": 100, "total": len(histories), "histories": histories}})
        return key

    def history(self, first: int, last: int, rate: float, sprint_for=None) -> None:
        """Closed tickets: on each day from first to last, about `rate` tickets close."""
        for offset in range(first, last + 1):
            for _ in range(self._count(rate)):
                work = self.rng.randint(1, 6)
                created = max(first - 5, offset - work - self.rng.randint(1, 10))
                started = offset - work
                sprints = [sprint_for(offset)] if sprint_for else []
                self.issue(created=created, moves=[(started, "In Progress"), (offset, "Done")],
                           priority=self.rng.choice(["High", "Medium", "Medium", "Low"]),
                           work_type=self.rng.choice(["Story", "Story", "Task", "Bug"]),
                           sprints=[s for s in sprints if s])

    def backlog(self, count: int, created_from: int, created_to: int) -> None:
        """Open tickets in the backlog: no sprint, no due date."""
        for _ in range(count):
            self.issue(created=self.rng.randint(created_from, created_to),
                       priority=self.rng.choice(["Medium", "Low", "Low", "Lowest"]))

    def _count(self, rate: float) -> int:
        whole = int(rate)
        return whole + (1 if self.rng.random() < rate - whole else 0)


def sprints_every_14_days(sid: int, prefix: str, first: int, board: int) -> list[dict]:
    result, start, number = [], first, 1
    while start <= 0:
        result.append(sprint(sid + number, f"{prefix} {number}", start, board=board))
        start += 14
        number += 1
    return result


def in_sprint(sprints: list[dict]):
    def find(offset: int):
        for s in sprints:
            start = (datetime.fromisoformat(s["startDate"]).astimezone(ZONE).date() - TODAY).days
            end = (datetime.fromisoformat(s["endDate"]).astimezone(ZONE).date() - TODAY).days
            if start <= offset < end:
                return s
        return None
    return find


def alpha(rng) -> dict:
    team = Team("ALP", "Alpha", rng)
    sprints = sprints_every_14_days(100, "ALP Sprint", -119, board=1)  # Active: -7 to +7
    active = sprints[-1]
    team.history(-115, -1, 0.6, in_sprint(sprints))
    s = [active]
    team.issue(created=-20, moves=[(-6, "In Progress"), (-2, "Blocked")], priority="Highest", due=5,
               sprints=s, title="Payment page fails for card type X", work_type="Bug")
    team.issue(created=-15, moves=[(-5, "In Progress")], priority="High", due=6, sprints=s,
               title="Export the monthly invoice as PDF")
    team.issue(created=-12, priority="Medium", due=1, sprints=s, title="Update the privacy text",
               work_type="Task")
    team.issue(created=-12, moves=[(-3, "In Progress")], priority="Medium", sprints=s,
               title="Show the order history on mobile")
    team.issue(created=-10, priority="Low", sprints=s, title="Add a dark mode")
    team.issue(created=-9, moves=[(-1, "In Review")], priority="High", due=3, sprints=s,
               title="Log in with a single sign-on account")
    team.issue(created=-30, moves=[(-4, "Done")], resolution="Won't Do", sprints=s,
               title="Old idea: fax export")
    team.backlog(12, -100, -20)
    return {"name": "Alpha", "issues": team.issues,
            "boards": [{"id": 1, "type": "scrum", "sprints": sprints}],
            "versions": [{"id": "11", "name": "2.3", "released": True, "archived": False,
                          "releaseDate": (TODAY - timedelta(days=21)).isoformat()},
                         {"id": "12", "name": "2.4", "released": False, "archived": False,
                          "releaseDate": "2026-12-15"}]}


def beta(rng) -> dict:
    team = Team("BET", "Beta", rng)
    web = sprints_every_14_days(200, "BET Web", -137, board=2)  # Active: -11 to +3
    mobile = [sprint(301, "BET Mobile 1", -4, board=2)]  # Active: -4 to +10
    team.history(-136, -1, 0.9, in_sprint(web))
    w, m = [web[-1]], [mobile[0]]
    team.issue(created=-25, moves=[(-9, "In Progress"), (-3, "Blocked")], priority="Medium",
               due=4, sprints=w, title="Sync the price list with the shop")
    team.issue(created=-25, moves=[(-8, "In Progress")], priority="Low", due=-2, sprints=w,
               title="Rename the export button", work_type="Task")
    team.issue(created=-14, priority="Medium", due=1, sprints=m, title="Push alerts on Android")
    team.issue(created=-14, moves=[(-2, "In Progress")], priority="High", due=5, sprints=m,
               title="Offline mode for the mobile app")
    team.issue(created=-10, moves=[(-1, "In Progress")], priority="Urgent", due=4, sprints=w,
               title="Hotfix for the cart total", work_type="Bug")
    team.issue(created=-8, priority="High", due=8, sprints=m, title="App store screenshots",
               work_type="Task")
    team.issue(created=-6, moves=[(-3, "In Progress")], priority="Medium", sprints=m,
               title="Dark mode for the mobile app")
    team.backlog(16, -120, -15)
    return {"name": "Beta", "issues": team.issues,
            "boards": [{"id": 2, "type": "scrum", "sprints": web + mobile}],
            "versions": [{"id": "21", "name": "Spring", "released": False, "archived": False,
                          "releaseDate": "2027-03-01"}]}


def gamma(rng) -> dict:
    team = Team("GAM", "Gamma", rng)
    team.history(-200, -1, 0.5)
    team.issue(created=-40, moves=[(-5, "In Progress")], priority="High", due=9,
               title="Move the help pages to the new site")
    team.issue(created=-30, moves=[(-2, "In Progress")], priority="Medium",
               title="Check the backup restore")
    team.issue(created=-3, priority="Low", due=12, title="Update the support hours")
    team.backlog(10, -150, -20)
    return {"name": "Gamma", "issues": team.issues,
            "boards": [{"id": 3, "type": "kanban"}],
            "versions": [{"id": "31", "name": "Next", "released": False, "archived": False}]}


def delta(rng) -> dict:
    team = Team("DEL", "Delta", rng)
    sprints = sprints_every_14_days(400, "DEL Sprint", -52, board=4)  # Active: -10 to +4
    team.history(-45, -14, 0.5, in_sprint(sprints))
    team.history(-13, -1, 0.25, in_sprint(sprints))
    s = [sprints[-1]]
    for offset, title in [(-12, "Set up the build pipeline"), (-11, "Design the data model"),
                          (-9, "Add the first API call"), (-8, "Write the README"),
                          (-6, "Plan the user tests"), (-5, "Make a test account"),
                          (-4, "Choose the chart library"), (-2, "Add error pages")]:
        team.issue(created=offset, priority="Medium", due=4 if offset > -5 else None, sprints=s,
                   moves=[(offset + 1, "In Progress")] if offset < -7 else (), title=title)
    return {"name": "Delta", "issues": team.issues,
            "boards": [{"id": 4, "type": "scrum", "sprints": sprints}],
            "versions": []}


def build() -> dict:
    rng = random.Random(SEED)
    return {
        "now": NOW.isoformat(),
        "note": "Made-up sample data for the SRG demo. Made by scripts/make_demo.py.",
        "statuses": [{"name": name, "statusCategory": {"name": category}}
                     for name, category in CATEGORY.items()],
        "fields": [{"id": SPRINT_FIELD, "name": "Sprint"}, {"id": FLAG_FIELD, "name": "Flagged"}],
        "projects": {"ALP": alpha(rng), "BET": beta(rng), "GAM": gamma(rng), "DEL": delta(rng)},
    }


def text() -> str:
    return json.dumps(build(), indent=1, ensure_ascii=False) + "\n"


def main() -> None:
    DATA_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(text(), encoding="utf-8")
    print(f"Wrote {DATA_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

