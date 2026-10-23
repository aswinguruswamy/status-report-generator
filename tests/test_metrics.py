"""Tests for the weekly numbers (SRG-19)."""

from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from status_report.config import load_config
from status_report.metrics import calculate, tickets_in_week
from status_report.models import StatusChange, Ticket

CONFIG = load_config(Path(__file__).resolve().parent.parent / "config.yaml")
TZ = ZoneInfo("America/Toronto")
START, END = date(2026, 10, 19), date(2026, 10, 25)  # Monday to Sunday


def at(day, hour=12, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


def change(when, old, new):
    category = {"To Do": "To Do", "In Progress": "In Progress", "Blocked": "In Progress",
                "Review": "In Progress", "Done": "Done"}
    return StatusChange(when, old, new, category.get(old), category[new])


def ticket(key="SRG-1", created=None, history=(), due=None, work_type="Story",
           labels=(), flagged=False):
    history = tuple(history)
    status = history[-1].to_status if history else "To Do"
    category = history[-1].to_category if history else "To Do"
    done = next((c.at for c in reversed(history) if c.to_category == "Done"), None)
    return Ticket(
        key=key, title="t", work_type=work_type, status=status, status_category=category,
        priority="High", assignee=None, due_date=due, created=created or at(19, 9),
        done_date=done if category == "Done" else None, resolved=None,
        labels=tuple(labels), flagged=flagged, history=history,
    )


def run(tickets, config=CONFIG, now=None):
    return calculate(tickets, config, START, END, now=now)


# --- Closed (D19) -------------------------------------------------------------

def test_closed_in_the_week():
    t = ticket(history=[change(at(20), "To Do", "Done")])
    assert run([t]).closed == ("SRG-1",)


def test_closed_at_2359_on_sunday_counts_in_that_week():
    t = ticket(history=[change(at(25, 23, 59), "In Progress", "Done")])
    assert run([t]).closed == ("SRG-1",)


def test_closed_at_0001_on_monday_counts_in_the_next_week():
    t = ticket(history=[change(at(26, 0, 1), "In Progress", "Done")])
    metrics = run([t])
    assert metrics.closed == ()
    assert metrics.open == ("SRG-1",)  # It was open at the end of the week


def test_closed_before_the_week_is_not_counted():
    t = ticket(created=at(5), history=[change(at(10), "To Do", "Done")])
    metrics = run([t])
    assert metrics.closed == () and metrics.open == ()


def test_reopened_in_the_week_is_open_not_closed():
    t = ticket(history=[change(at(20), "To Do", "Done"), change(at(22), "Done", "In Progress")])
    metrics = run([t])
    assert metrics.closed == () and metrics.open == ("SRG-1",)


def test_resolved_date_is_second_check_when_no_history():
    t = replace(ticket(), status="Done", status_category="Done", done_date=at(21))
    assert run([t]).closed == ("SRG-1",)


# --- Opened -------------------------------------------------------------------

def test_opened_this_week():
    tickets = [ticket("SRG-1", created=at(19, 0, 0)), ticket("SRG-2", created=at(18, 23, 59))]
    assert run(tickets).opened == ("SRG-1",)


def test_ticket_created_after_the_week_is_not_counted():
    t = ticket(created=at(26, 9))
    metrics = run([t])
    assert metrics.opened == () and metrics.open == ()


# --- Open, overdue -----------------------------------------------------------

def test_open_at_the_end_of_the_week():
    tickets = [ticket("SRG-1"), ticket("SRG-2", history=[change(at(21), "To Do", "Done")])]
    assert run(tickets).open == ("SRG-1",)


def test_overdue_open_ticket():
    tickets = [ticket("SRG-1", due=date(2026, 10, 23)),
               ticket("SRG-2", due=date(2026, 10, 30)),
               ticket("SRG-3", due=date(2026, 10, 21),
                      history=[change(at(20), "To Do", "Done")])]
    assert run(tickets).overdue == ("SRG-1",)


def test_due_on_sunday_and_open_at_the_end_of_the_week_is_overdue():
    assert run([ticket(due=date(2026, 10, 25))]).overdue == ("SRG-1",)


def test_current_week_compares_with_today():
    t = ticket(due=date(2026, 10, 23))  # Friday
    assert run([t], now=at(22)).overdue == ()  # Thursday: not late yet
    assert run([t], now=at(24)).overdue == ("SRG-1",)  # Saturday: late


# --- Blocked and days blocked -------------------------------------------------

def test_blocked_by_status_and_days_blocked():
    t = ticket(history=[change(at(20, 12), "To Do", "In Progress"),
                        change(at(22, 12), "In Progress", "Blocked")])
    metrics = run([t])
    assert metrics.blocked == ("SRG-1",)
    assert metrics.days_blocked["SRG-1"] == 3  # Thursday noon to Monday 00:00


def test_unblocked_before_the_end_of_the_week():
    t = ticket(history=[change(at(20), "To Do", "Blocked"), change(at(23), "Blocked", "In Progress")])
    assert run([t]).blocked == ()


def test_blocked_by_label_and_flag_have_no_days():
    config = replace(CONFIG, blocked_methods=("label", "flag"))
    tickets = [ticket("SRG-1", labels=("Blocked",)), ticket("SRG-2", flagged=True), ticket("SRG-3")]
    metrics = run(tickets, config)
    assert metrics.blocked == ("SRG-1", "SRG-2")
    assert metrics.days_blocked == {"SRG-1": None, "SRG-2": None}


def test_flag_is_ignored_when_not_a_blocked_method():
    assert run([ticket(flagged=True)]).blocked == ()


def test_done_ticket_is_never_blocked_or_overdue():
    t = ticket(due=date(2026, 10, 20), labels=("blocked",),
               history=[change(at(21), "Blocked", "Done")])
    metrics = run([t], replace(CONFIG, blocked_methods=("status", "label")))
    assert metrics.blocked == () and metrics.overdue == ()


# --- Work types (D23) and no negative numbers ---------------------------------

def test_only_work_types_from_config_are_counted():
    tickets = [ticket("SRG-1"), ticket("SRG-2", work_type="Epic"),
               ticket("SRG-3", work_type="Subtask")]
    assert run(tickets).counts() == {"closed": 0, "opened": 1, "open": 1,
                                     "blocked": 0, "overdue": 0}


def test_no_tickets_gives_zero_and_no_number_is_negative():
    counts = run([]).counts()
    assert counts == {"closed": 0, "opened": 0, "open": 0, "blocked": 0, "overdue": 0}
    assert all(value >= 0 for value in counts.values())


def test_days_blocked_is_never_negative():
    t = ticket(created=at(20), history=[change(at(25, 23, 59), "To Do", "Blocked")])
    assert run([t]).days_blocked["SRG-1"] == 0


# --- Exact week filter in the local time zone (SRG-33, C3) ---------------------

def test_report_shows_only_tickets_of_the_week():
    tickets = [
        ticket("SRG-1"),  # open
        ticket("SRG-2", created=at(5), history=[change(at(10), "To Do", "Done")]),  # old
        ticket("SRG-3", created=at(26, 9)),  # after the week
        ticket("SRG-4", created=at(25, 23, 30)),  # Sunday 23:30 local time
    ]
    metrics = run(tickets)
    assert [t.key for t in tickets_in_week(tickets, metrics)] == ["SRG-1", "SRG-4"]
