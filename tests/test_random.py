"""Survival checks on random weeks (SRG-22, D18).

Each seed makes a difficult week. After each run the tool must survive and keep its
rules. When a seed fails, its week is saved in tests/regressions/ and then runs in
each later test run as a permanent test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from generator import WEEK_END, WEEK_START, load_week, make_week, save_week
from test_metrics import CONFIG

from status_report.metrics import calculate, tickets_in_week
from status_report.project import project_status
from status_report.report import SECTIONS, to_html, to_markdown

SEEDS = range(300)
REGRESSIONS = Path(__file__).parent / "regressions"
NOW_VALUES = [None, datetime(2026, 10, 22, 16, tzinfo=UTC)]  # Finished week, current week


def check_week(tickets) -> None:
    """All survival checks. Raises AssertionError on the first broken rule."""
    for now in NOW_VALUES:
        metrics = calculate(tickets, CONFIG, WEEK_START, WEEK_END, now=now)
        week = tickets_in_week(tickets, metrics)
        status = project_status(week, metrics, CONFIG)
        markdown = to_markdown(week, metrics, status, "SIM")
        page = to_html(week, metrics, status, "SIM")

        # 1. The project status is only Red, Amber, or Green.
        assert status.status in {"Red", "Amber", "Green"}
        assert status.reason.startswith(f"{status.status}: ")
        # 2. No count is less than zero.
        assert all(value >= 0 for value in metrics.counts().values())
        assert all(d is None or d >= 0 for d in metrics.days_blocked.values())
        # 3. The report has all sections.
        for section in SECTIONS:
            assert f"## {section}" in markdown and f"<h2>{section}</h2>" in page
        # 4. The numbers agree with each other.
        assert not set(metrics.open) & set(metrics.closed)
        assert set(metrics.blocked) <= set(metrics.open)
        assert set(metrics.overdue) <= set(metrics.open)
        assert set(status.ticket_status) == set(metrics.open)
        assert sum(sum(row.values()) for row in status.counts().values()) == len(metrics.open)
        # 5. Only the counted work types (D23) and no unsafe HTML.
        counted = {t.key for t in tickets if t.work_type in CONFIG.work_types}
        assert {t.key for t in week} <= counted
        assert "<script>" not in page


@pytest.mark.parametrize("seed", SEEDS)
def test_random_week_survives(seed):
    tickets = make_week(seed)
    try:
        check_week(tickets)
    except Exception:
        save_week(tickets, REGRESSIONS / f"seed-{seed}.json")
        raise


@pytest.mark.parametrize(
    "path", sorted(REGRESSIONS.glob("*.json")), ids=lambda p: p.stem
)
def test_saved_failure_stays_fixed(path):
    check_week(load_week(path))


def test_generator_is_repeatable_and_difficult():
    assert make_week(7) == make_week(7)
    weeks = [make_week(seed) for seed in SEEDS]
    tickets = [t for week in weeks for t in week]
    assert any(len(week) == 0 for week in weeks)  # Empty week
    assert any(len(week) > 100 for week in weeks)  # More than 100 tickets
    assert any(t.due_date is None for t in tickets)  # No due date
    assert any(t.created.year == 1990 for t in tickets)  # Very old date
    assert any("<script>" in t.title or "|" in t.title for t in tickets)  # Special characters
    assert any(t.story_points for t in tickets)  # Story points (D20)
    people = {t.assignee for t in tickets if t.assignee}
    assert 1 < len(people) <= 25  # Simulated teams of up to 25 people


def test_save_and_load_keep_the_week(tmp_path):
    week = make_week(3)
    save_week(week, tmp_path / "week.json")
    assert load_week(tmp_path / "week.json") == week
