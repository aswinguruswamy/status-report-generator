"""Make the sample report in examples/ from simulated data (SRG-29).

The data is a made-up project "DEMO". It is not this project (D20).
Run it after a change to the report layout:

    python scripts/make_sample.py

A test checks that the files in examples/ are the same as the output of this script.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from status_report.ai import build_ai_input, check_answer
from status_report.config import load_config
from status_report.metrics import calculate, tickets_in_week
from status_report.models import StatusChange, Ticket
from status_report.project import project_status
from status_report.report import AI_NOTE, report_name, to_html, to_markdown

ROOT = Path(__file__).resolve().parent.parent
FOLDER = ROOT / "examples"
START, END = date(2026, 10, 19), date(2026, 10, 25)
GENERATED = date(2026, 10, 26)
AI_NOTE_SAMPLE = ("Sample text, written for this example in the form of an AI answer. In a real "
                  "report, the AI writes it from the facts. The rules set the status, not the AI (D02).")
CATEGORY = {"To Do": "To Do", "In Progress": "In Progress", "Blocked": "In Progress",
            "Review": "In Progress", "Done": "Done"}


def at(day: int, hour: int = 10) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def move(day: int, old: str, new: str) -> StatusChange:
    return StatusChange(at(day), old, new, CATEGORY[old], CATEGORY[new])


def demo(key, title, priority, owner, created, moves=(), due=None, work_type="Story") -> Ticket:
    status = moves[-1].to_status if moves else "To Do"
    done = [m.at for m in moves if m.to_category == "Done"]
    return Ticket(
        key=key, title=title, work_type=work_type, status=status, status_category=CATEGORY[status],
        priority=priority, assignee=owner, due_date=due, created=created,
        done_date=done[-1] if done else None, resolved=None, labels=(), flagged=False,
        history=tuple(moves), story_points=None,
    )


def tickets() -> list[Ticket]:
    old = datetime(2026, 10, 5, 9, tzinfo=UTC)
    return [
        demo("DEMO-101", "Payment page fails for card type X", "Highest", "Priya N", old,
             [move(14, "To Do", "In Progress"), move(20, "In Progress", "Blocked")], work_type="Bug"),
        demo("DEMO-102", "Export the monthly invoice as PDF", "High", "Tom R", old,
             [move(12, "To Do", "In Progress")], due=date(2026, 10, 22)),
        demo("DEMO-103", "Add a search filter for orders", "High", None, old, due=date(2026, 10, 26)),
        demo("DEMO-104", "Update the privacy text", "Medium", "Lena K", old,
             [move(13, "To Do", "In Progress"), move(21, "In Progress", "Blocked")], work_type="Task"),
        demo("DEMO-105", "Show the order history on mobile", "Medium", "Tom R", old,
             [move(15, "To Do", "In Progress")], due=date(2026, 10, 30)),
        demo("DEMO-106", "Fix the date format in emails", "Low", "Priya N", at(19),
             [move(20, "To Do", "In Progress"), move(22, "In Progress", "Done")], work_type="Bug"),
        demo("DEMO-107", "Log in with a single sign-on account", "High", "Lena K", old,
             [move(9, "To Do", "In Progress"), move(21, "In Progress", "Done")]),
        demo("DEMO-108", "Write the release notes for 2.4", "Low", "Sam O", at(20), work_type="Task"),
        demo("DEMO-109", "Speed up the report page", "Medium", "Sam O", old,
             [move(16, "To Do", "In Progress"), move(23, "In Progress", "Done")]),
        demo("DEMO-110", "Add a dark mode", "Lowest", None, at(21)),
    ]


SUMMARY_ANSWER = {
    "summary": "The project is Red. DEMO-101 has the P1 priority and is blocked. DEMO-102 is "
               "overdue, and DEMO-104 is blocked. The team closed 3 tickets and opened 3.",
    "next_week": ["Remove the blocker on DEMO-101.", "Finish DEMO-102.",
                  "Remove the blocker on DEMO-104."],
}


def build() -> dict[str, str]:
    config = load_config(ROOT / "config.yaml")
    all_tickets = tickets()
    metrics = calculate(all_tickets, config, START, END)
    week = tickets_in_week(all_tickets, metrics)
    status = project_status(week, metrics, config)
    ai_input = build_ai_input(week, metrics, status, config)
    # The sample text passes the same checks as a real AI answer (D36, D41, D44).
    summary = check_answer(json.dumps(SUMMARY_ANSWER), ai_input)
    name = report_name("DEMO", START)
    md = to_markdown(week, metrics, status, "DEMO", summary, generated=GENERATED)
    page = to_html(week, metrics, status, "DEMO", summary, generated=GENERATED)
    return {
        f"{name}.md": md.replace(AI_NOTE, AI_NOTE_SAMPLE),
        f"{name}.html": page.replace(AI_NOTE, AI_NOTE_SAMPLE),
    }


def main() -> None:
    FOLDER.mkdir(exist_ok=True)
    for file_name, text in build().items():
        (FOLDER / file_name).write_text(text, encoding="utf-8")
        print(f"Wrote examples/{file_name}")


if __name__ == "__main__":
    main()
