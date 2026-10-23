"""Tests for the ticket status rules (SRG-20, D21, D22)."""

from dataclasses import replace
from datetime import date

from test_metrics import CONFIG, at, change, ticket

from status_report.metrics import calculate
from status_report.models import StatusChange
from status_report.status import AMBER, BLACK, GREEN, RED, ticket_statuses

START, END = date(2026, 10, 19), date(2026, 10, 25)
THURSDAY = at(22)  # "today" for the current-week tests: Thursday Oct 22, noon


def statuses(tickets, config=CONFIG, now=THURSDAY):
    metrics = calculate(tickets, config, START, END, now=now)
    return ticket_statuses(tickets, metrics, config)


def in_progress(day=20):
    return [change(at(day), "To Do", "In Progress")]


def blocked(day=21):
    return [change(at(day), "To Do", "Blocked")]


# --- Rule 1: Black -----------------------------------------------------------

def test_overdue_is_black():
    assert statuses([ticket(due=date(2026, 10, 21), history=in_progress())]) == {"SRG-1": BLACK}


def test_overdue_and_blocked_is_black():
    assert statuses([ticket(due=date(2026, 10, 21), history=blocked())]) == {"SRG-1": BLACK}


# --- Rule 2: Red ---------------------------------------------------------------

def test_blocked_and_not_overdue_is_red():
    assert statuses([ticket(due=date(2026, 10, 30), history=blocked())]) == {"SRG-1": RED}


def test_blocked_and_due_soon_in_to_do_is_red_not_amber():
    t = ticket(due=date(2026, 10, 23), history=blocked())
    assert statuses([t]) == {"SRG-1": RED}


# --- Rule 3: Amber (D22) -------------------------------------------------------

def test_due_in_2_days_and_still_in_to_do_is_amber():
    for due in (date(2026, 10, 22), date(2026, 10, 23), date(2026, 10, 24)):
        assert statuses([ticket(due=due)]) == {"SRG-1": AMBER}, due


def test_due_in_3_days_is_green():
    assert statuses([ticket(due=date(2026, 10, 25))]) == {"SRG-1": GREEN}


def test_in_progress_near_the_due_date_is_green():
    assert statuses([ticket(due=date(2026, 10, 23), history=in_progress())]) == {"SRG-1": GREEN}


def test_amber_uses_the_status_category_not_the_name():
    # A team calls its first status "Backlog". Its category is still "To Do".
    renamed = StatusChange(at(20), "Open", "Backlog", "To Do", "To Do")
    assert statuses([ticket(due=date(2026, 10, 23), history=[renamed])]) == {"SRG-1": AMBER}


def test_amber_window_comes_from_config():
    config = replace(CONFIG, amber_window_days=5)
    assert statuses([ticket(due=date(2026, 10, 27))], config) == {"SRG-1": AMBER}


# --- Rule 4: Green and special cases ------------------------------------------

def test_no_due_date_is_never_black_or_amber():
    assert statuses([ticket()]) == {"SRG-1": GREEN}
    assert statuses([ticket(history=blocked())]) == {"SRG-1": RED}


def test_done_ticket_has_no_status():
    t = ticket(due=date(2026, 10, 20), history=[change(at(21), "In Progress", "Done")])
    assert statuses([t]) == {}


def test_finished_week_uses_the_monday_after():
    # Report made later for the full week: today = Monday Oct 26.
    tickets = [ticket("SRG-1", due=date(2026, 10, 25)), ticket("SRG-2", due=date(2026, 10, 27))]
    assert statuses(tickets, now=None) == {"SRG-1": BLACK, "SRG-2": AMBER}


def test_each_open_ticket_gets_exactly_one_status():
    tickets = [ticket("SRG-1"), ticket("SRG-2", due=date(2026, 10, 20)),
               ticket("SRG-3", history=blocked()), ticket("SRG-4", due=date(2026, 10, 23))]
    result = statuses(tickets)
    assert result == {"SRG-1": GREEN, "SRG-2": BLACK, "SRG-3": RED, "SRG-4": AMBER}
