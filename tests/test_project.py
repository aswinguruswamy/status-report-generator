"""Tests for the priority matrix and the project status (SRG-21, D21)."""

from dataclasses import replace
from datetime import date

from test_metrics import CONFIG, at, change, ticket

from status_report.metrics import calculate
from status_report.project import project_status

START, END = date(2026, 10, 19), date(2026, 10, 25)
THURSDAY = at(22)


def project(tickets, config=CONFIG, now=THURSDAY):
    metrics = calculate(tickets, config, START, END, now=now)
    return project_status(tickets, metrics, config)


def t(key, priority, due=None, history=(), created=None):
    return replace(ticket(key, due=due, history=history, created=created or at(19, 9)),
                   priority=priority)


def blocked():
    return [change(at(21), "To Do", "Blocked")]


def closed():
    return [change(at(21), "To Do", "Done")]


def old_ticket(key, priority, **kwargs):
    return t(key, priority, created=at(5), **kwargs)  # Not opened this week


# --- Matrix -------------------------------------------------------------------

def test_matrix_counts_status_against_priority():
    tickets = [old_ticket("SRG-1", "Highest", history=blocked()),
               old_ticket("SRG-2", "Lowest", history=blocked()),
               old_ticket("SRG-3", "High", due=date(2026, 10, 23)),
               old_ticket("SRG-4", "Low")]
    counts = project(tickets).counts()
    assert counts["Red"]["P1"] == 1 and counts["Red"]["P5"] == 1
    assert counts["Amber"]["P2"] == 1
    assert counts["Green"]["P4"] == 1
    assert sum(sum(row.values()) for row in counts.values()) == 4


def test_unknown_priority_is_in_the_unmapped_column_with_a_warning():
    result = project([old_ticket("SRG-1", "Critical")])
    assert result.matrix["Green"]["Unmapped"] == ["SRG-1"]
    assert "SRG-1" in result.warnings[0] and "Critical" in result.warnings[0]


# --- Project Red ----------------------------------------------------------------

def test_red_when_a_p1_ticket_is_blocked():
    result = project([old_ticket("SRG-12", "Highest", history=blocked())])
    assert result.status == "Red"
    assert result.reason == "Red: 1 P1 ticket is blocked (SRG-12)."


def test_red_when_a_p2_ticket_is_overdue():
    result = project([old_ticket("SRG-5", "High", due=date(2026, 10, 20))])
    assert result.reason == "Red: 1 P2 ticket is overdue (SRG-5)."


# --- Project Amber --------------------------------------------------------------

def test_amber_when_a_low_priority_ticket_is_red():
    result = project([old_ticket("SRG-7", "Lowest", history=blocked())])
    assert result.status == "Amber"
    assert result.reason == "Amber: 1 P5 ticket is blocked (SRG-7)."


def test_amber_when_a_high_priority_ticket_is_amber():
    result = project([old_ticket("SRG-8", "Highest", due=date(2026, 10, 23))])
    assert result.reason == "Amber: 1 P1 ticket is due soon and not started (SRG-8)."


def test_amber_when_the_team_closed_fewer_than_it_opened():
    tickets = [t("SRG-1", "Medium"), t("SRG-2", "Medium"), t("SRG-3", "Medium", history=closed())]
    result = project(tickets)
    assert result.status == "Amber"
    assert result.reason == "Amber: The team closed 1 and opened 3 tickets."


def test_unmapped_red_ticket_makes_amber_not_red():
    assert project([old_ticket("SRG-1", "Critical", history=blocked())]).status == "Amber"


# --- Project Green --------------------------------------------------------------

def test_green_when_nothing_is_wrong():
    tickets = [old_ticket("SRG-1", "Highest"), old_ticket("SRG-2", "Low", history=closed())]
    result = project(tickets)
    assert result.status == "Green"
    assert result.reason == "Green: No blocked, overdue, or at-risk tickets."


def test_empty_week_is_green_with_no_open_tickets():
    result = project([])
    assert result.status == "Green"
    assert result.reason == "Green: No open tickets."


# --- Order and limits -------------------------------------------------------------

def test_red_wins_over_amber():
    tickets = [old_ticket("SRG-1", "High", history=blocked()),
               old_ticket("SRG-2", "Lowest", history=blocked())]
    result = project(tickets)
    assert result.status == "Red"
    assert "SRG-2" not in result.reason


def test_project_status_is_never_black():
    for tickets in ([old_ticket("SRG-1", "Highest", due=date(2026, 10, 1))], []):
        assert project(tickets).status in {"Red", "Amber", "Green"}


def test_high_priorities_come_from_config():
    config = replace(CONFIG, high_priorities=("P1",))
    assert project([old_ticket("SRG-1", "High", history=blocked())], config).status == "Amber"


def test_two_tickets_use_the_plural():
    tickets = [old_ticket("SRG-1", "Highest", history=blocked()),
               old_ticket("SRG-2", "Highest", history=blocked())]
    assert project(tickets).reason == "Red: 2 P1 tickets are blocked (SRG-1, SRG-2)."


# --- Reason length (SRG-36, D43) ---------------------------------------------------------

def test_reason_names_at_most_3_keys_for_40_tickets():
    tickets = [old_ticket(f"SRG-{n}", "Highest", history=blocked()) for n in range(1, 41)]
    result = project(tickets)
    assert result.reason == "Red: 40 P1 tickets are blocked (SRG-1, SRG-2, SRG-3, and 37 more)."
    assert len(result.reason) < 80
    assert sum(result.counts()["Red"].values()) == 40  # The counts stay exact
    assert len(result.matrix["Red"]["P1"]) == 40  # The full list stays for the report table


def test_exactly_3_keys_has_no_more_text():
    tickets = [old_ticket(f"SRG-{n}", "Highest", history=blocked()) for n in range(1, 4)]
    assert project(tickets).reason == "Red: 3 P1 tickets are blocked (SRG-1, SRG-2, SRG-3)."


def test_ai_accepts_each_key_in_the_input_when_the_reason_is_short():
    import json

    from status_report.ai import build_ai_input, check_answer

    tickets = [old_ticket(f"SRG-{n}", "Highest", history=blocked()) for n in range(1, 41)]
    metrics = calculate(tickets, CONFIG, START, END, now=THURSDAY)
    status = project_status(tickets, metrics, CONFIG)
    ai_input = build_ai_input(tickets, metrics, status, CONFIG)
    answer = {
        "summary": "The project is Red. SRG-40 is blocked. SRG-25 is blocked too.",
        "next_week": ["Free SRG-40 and SRG-25."],
    }
    assert check_answer(json.dumps(answer), ai_input).next_week == ("Free SRG-40 and SRG-25.",)
