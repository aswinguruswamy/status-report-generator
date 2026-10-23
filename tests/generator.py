"""Random generator for simulated teams (SRG-22, D18, D20).

It makes difficult weeks on purpose: no due dates, very old dates, special characters,
empty weeks, and more than 100 tickets. The same seed always makes the same week.
The simulated numbers test the tool. They never describe this project (D20).
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from status_report.models import StatusChange, Ticket

WEEK_START, WEEK_END = date(2026, 10, 19), date(2026, 10, 25)
STATUSES = {  # name -> status category
    "To Do": "To Do", "Backlog": "To Do", "In Progress": "In Progress",
    "Blocked": "In Progress", "Review": "In Progress", "Done": "Done", "Closed": "Done",
}
PRIORITIES = ["Highest", "High", "Medium", "Low", "Lowest", "Critical", None]
WORK_TYPES = ["Story", "Task", "Bug", "Epic", "Subtask"]
TITLES = [
    "Add login page", "Fix | pipe in title", "<script>alert(1)</script>", "Ünïcødé ✓ 日本語",
    "", "Line one\nline two", "a" * 300, "Quote \" and ' and `", "Emoji 🚀 release",
]
POINTS = [None, 1, 2, 3, 5, 8, 13]


def _moment(rng: random.Random) -> datetime:
    """A time near the week, sometimes very old or far in the future."""
    roll = rng.random()
    if roll < 0.05:
        base = datetime(1990, 1, 1, tzinfo=UTC)  # Very old
    elif roll < 0.10:
        base = datetime(2030, 1, 1, tzinfo=UTC)  # Far in the future
    else:
        base = datetime(2026, 10, 1, tzinfo=UTC)
    return base + timedelta(minutes=rng.randint(0, 60 * 24 * 40))


def _history(rng: random.Random, created: datetime) -> tuple[StatusChange, ...]:
    changes, current, at = [], "To Do", created
    for _ in range(rng.randint(0, 6)):
        at = at + timedelta(minutes=rng.randint(1, 60 * 24 * 5))
        new = rng.choice([s for s in STATUSES if s != current])
        changes.append(StatusChange(at, current, new, STATUSES[current], STATUSES[new]))
        current = new
    return tuple(changes)


def make_ticket(rng: random.Random, number: int, team: list[str]) -> Ticket:
    created = _moment(rng)
    history = _history(rng, created)
    status = history[-1].to_status if history else "To Do"
    category = STATUSES[status]
    done_moves = [c.at for c in history if c.to_category == "Done"]
    due = None if rng.random() < 0.3 else (_moment(rng).date())
    return Ticket(
        key=f"SIM-{number}",
        title=rng.choice(TITLES),
        work_type=rng.choice(WORK_TYPES),
        status=status,
        status_category=category,
        priority=rng.choice(PRIORITIES),
        assignee=rng.choice(team) if team and rng.random() < 0.8 else None,
        due_date=due,
        created=created,
        done_date=done_moves[-1] if category == "Done" and done_moves else None,
        resolved=None,
        labels=tuple(rng.sample(["blocked", "Blocked", "ux", "api"], rng.randint(0, 2))),
        flagged=rng.random() < 0.1,
        history=history,
        story_points=rng.choice(POINTS),
    )


def make_week(seed: int) -> list[Ticket]:
    """A simulated team of 0 to 25 people with 0 to 250 tickets."""
    rng = random.Random(seed)
    team = [f"Person {n}" for n in range(rng.randint(0, 25))]
    size = rng.choice([0, 1, 5, 30, 101, 250])  # Empty weeks and more than 100 tickets
    return [make_ticket(rng, n, team) for n in range(1, size + 1)]


# --- Save a failing week as a permanent test (D18) ------------------------------

def save_week(tickets: list[Ticket], path: Path) -> None:
    def encode(value):
        if isinstance(value, datetime | date):
            return value.isoformat()
        raise TypeError(type(value))

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(t) for t in tickets], default=encode, indent=1))


def load_week(path: Path) -> list[Ticket]:
    tickets = []
    for raw in json.loads(path.read_text()):
        raw["history"] = tuple(
            StatusChange(datetime.fromisoformat(c["at"]), c["from_status"], c["to_status"],
                         c["from_category"], c["to_category"])
            for c in raw["history"]
        )
        for name in ("created", "done_date", "resolved"):
            raw[name] = datetime.fromisoformat(raw[name]) if raw[name] else None
        raw["due_date"] = date.fromisoformat(raw["due_date"]) if raw["due_date"] else None
        raw["labels"] = tuple(raw["labels"])
        tickets.append(Ticket(**raw))
    return tickets
