"""v2 colours: ticket colour, team colour and reason (spec SRG-R5–R7, R9, R10, R13.4; plan S5)."""

from __future__ import annotations

import random

from v2_tickets import CONFIG, NOW, SPRINT, TODAY, ticket

from status_report.metrics import colour_scope, window_counts
from status_report.project import GREEN_EMPTY, GREEN_OK, team_status
from status_report.status import BLOCKED, DUE_SOON, NO_DUE_DATE, OVERDUE, ticket_colour


def colour(t):
    result = ticket_colour(t, CONFIG, TODAY)
    return result.colour if result else None


def team(tickets, closed=0, opened=0):
    return team_status(tickets, closed, opened, CONFIG, TODAY)


# --- Ticket colour (R6.1) --------------------------------------------------------------


def test_ac5_due_yesterday_is_black():
    assert colour(ticket(due=-1)) == "Black"


def test_ac6_blocked_due_in_10_days_is_red():
    assert colour(ticket(status="Blocked", due=10)) == "Red"


def test_ac7_due_tomorrow_to_do_is_amber():
    assert colour(ticket(status="To Do", due=1)) == "Amber"


def test_ac8_due_tomorrow_in_progress_is_green():
    assert colour(ticket(status="In Progress", due=1)) == "Green"


def test_ac9_no_due_date_sprint_ended_yesterday_is_black():
    from v2_tickets import sprint

    assert colour(ticket(due=None, sprints=(sprint(5, -1, "closed"),))) == "Black"


def test_ac10_no_date_no_sprint_high_is_amber():
    result = ticket_colour(ticket(due=None, sprints=(), priority="High"), CONFIG, TODAY)
    assert (result.colour, result.cause) == ("Amber", NO_DUE_DATE)


def test_ac11_no_date_no_sprint_medium_is_green():
    assert colour(ticket(due=None, sprints=(), priority="Medium")) == "Green"


def test_ac12_blocked_wins_over_no_date_high():
    assert colour(ticket(status="Blocked", due=None, sprints=(), priority="High")) == "Red"


def test_blocked_and_overdue_is_black():
    assert colour(ticket(status="Blocked", due=-3)) == "Black"


def test_due_today_and_window_edge():
    assert colour(ticket(due=0)) == "Amber"
    assert colour(ticket(due=2)) == "Amber"  # amber_window_days = 2
    assert colour(ticket(due=3)) == "Green"


def test_sprint_end_is_the_effective_date_for_amber():
    from v2_tickets import sprint

    assert colour(ticket(due=None, sprints=(sprint(5, 1),))) == "Amber"


def test_done_and_cleaned_up_tickets_have_no_colour():
    assert colour(ticket(status="Done", due=-5)) is None
    assert colour(ticket(status="Done", resolution="Won't Do", due=-5)) is None


def test_causes():
    assert ticket_colour(ticket(due=-1), CONFIG, TODAY).cause == OVERDUE
    assert ticket_colour(ticket(status="Blocked"), CONFIG, TODAY).cause == BLOCKED
    assert ticket_colour(ticket(due=1), CONFIG, TODAY).cause == DUE_SOON
    assert ticket_colour(ticket(due=8), CONFIG, TODAY).cause is None


# --- Team colour (R7.1) and reason (R10) ----------------------------------------------


def test_ac18_one_high_ticket_overdue_is_red():
    tickets = [ticket("BET-7", priority="High", due=-1)] + [ticket(f"BET-{n}", due=9) for n in (1, 2)]
    result = team(tickets)
    assert result.colour == "Red"
    assert result.reason == "Red: 1 P2 ticket is overdue (BET-7)."


def test_ac19_one_low_ticket_blocked_is_amber():
    tickets = [ticket("BET-3", priority="Low", status="Blocked", due=9), ticket("BET-4", due=9)]
    result = team(tickets, closed=3, opened=3)
    assert result.colour == "Amber"
    assert result.reason == "Amber: 1 P4 ticket is blocked (BET-3)."


def test_ac20_one_low_ticket_amber_is_green():
    tickets = [ticket("BET-3", priority="Low", due=1), ticket("BET-4", due=9)]
    result = team(tickets, closed=3, opened=2)
    assert result.colour == "Green" and result.reason == GREEN_OK


def test_ac21_one_high_ticket_amber_is_amber():
    tickets = [ticket("BET-3", priority="Highest", due=1), ticket("BET-4", due=9)]
    result = team(tickets, closed=5, opened=1)
    assert result.colour == "Amber"
    assert result.reason == "Amber: 1 P1 ticket is due soon and not started (BET-3)."


def test_high_ticket_with_no_date_makes_the_team_amber():
    result = team([ticket("BET-3", priority="High", sprints=())])
    assert result.reason == "Amber: 1 P2 ticket has no due date (BET-3)."


def test_ac22_four_p1_tickets_blocked_names_3_and_1_more():
    tickets = [ticket(f"A-{n}", priority="Highest", status="Blocked", due=9) for n in (4, 2, 3, 1)]
    assert team(tickets).reason == "Red: 4 P1 tickets are blocked (A-1, A-2, A-3, and 1 more)."


def test_ac23_no_open_tickets():
    result = team([ticket("BET-1", status="Done")])
    assert result.colour == "Green" and result.reason == GREEN_EMPTY == "Green: No open tickets."


def test_ac13_closed_fewer_than_opened_is_amber_and_duplicates_do_not_count():
    opened = [ticket(f"BET-{n}", created=-3, sprints=()) for n in range(1, 11)]
    closed = [ticket(f"BET-{n}", status="Done", created=-40, closed=-2, sprints=())
              for n in range(11, 15)]
    duplicates = [ticket(f"BET-{n}", status="Done", resolution="Duplicate", created=-90,
                         closed=-2, sprints=()) for n in range(15, 23)]
    sprint_tickets = [ticket("BET-30", due=9), ticket("BET-31", status="In Progress", due=1)]
    project = opened + closed + duplicates + sprint_tickets
    closed_n, opened_n = window_counts(project, CONFIG, NOW)
    assert (closed_n, opened_n) == (4, 10)
    scope = colour_scope(project, {SPRINT.id}, CONFIG, NOW)
    result = team(scope.tickets, closed_n, opened_n)
    assert result.colour == "Amber"
    assert "closed 4 and opened 10" in result.reason
    assert result.reason == ("Amber: The team closed 4 and opened 10 tickets in the last 14 days.")


def test_reason_parts_follow_the_rule_order():
    tickets = [
        ticket("BET-1", priority="Low", due=-1),  # Other Black
        ticket("BET-2", priority="Medium", status="Blocked", due=9),  # Other Red
        ticket("BET-3", priority="High", due=1),  # High Amber, due soon
        ticket("BET-4", priority="Highest", sprints=()),  # High Amber, no date
    ]
    assert team(tickets, closed=1, opened=2).reason == (
        "Amber: 1 P4 ticket is overdue (BET-1); 1 P3 ticket is blocked (BET-2); "
        "1 P2 ticket is due soon and not started (BET-3); 1 P1 ticket has no due date (BET-4); "
        "the team closed 1 and opened 2 tickets in the last 14 days."
    )


def test_red_reason_names_only_the_red_rule():
    tickets = [ticket("BET-1", priority="High", status="Blocked", due=9),
               ticket("BET-2", priority="Highest", due=-2),
               ticket("BET-3", priority="Low", due=-2)]
    assert team(tickets, closed=0, opened=5).reason == (
        "Red: 1 P1 ticket is overdue (BET-2); 1 P2 ticket is blocked (BET-1)."
    )


def test_team_is_never_black():
    tickets = [ticket(f"BET-{n}", priority="Highest", due=-5) for n in range(1, 4)]
    assert team(tickets).colour == "Red"


def test_ac41_unknown_priority_is_not_high_and_gives_a_warning():
    tickets = [ticket("BET-5", priority="Urgent", status="Blocked", due=9)]
    result = team(tickets)
    assert result.colour == "Amber"  # Blocked, but not high priority
    assert result.reason == "Amber: 1 Unmapped ticket is blocked (BET-5)."
    assert len(result.warnings) == 1 and "BET-5" in result.warnings[0]
    assert "Urgent" in result.warnings[0]


def test_unknown_priority_with_no_date_is_green():
    assert colour(ticket(priority="Urgent", sprints=())) == "Green"


# --- Same input, same output (AC16, N2) -------------------------------------------------


def random_tickets(seed: int):
    rng = random.Random(seed)
    tickets = []
    for n in range(1, rng.randint(1, 40)):
        tickets.append(ticket(
            f"BET-{n}",
            status=rng.choice(["To Do", "In Progress", "Blocked", "Done"]),
            priority=rng.choice(["Highest", "High", "Medium", "Low", "Lowest", "Urgent", None]),
            due=rng.choice([None, -3, -1, 0, 1, 2, 5]),
            created=rng.randint(-30, 0),
            sprints=rng.choice([(SPRINT,), ()]),
            resolution=rng.choice([None, None, "Won't Do"]),
        ))
    return tickets


def test_ac16_same_data_gives_the_same_colours_and_reasons():
    for seed in range(200):
        first = team(random_tickets(seed), 3, 4)
        again = team(list(reversed(random_tickets(seed))), 3, 4)
        assert (first.colour, first.reason) == (again.colour, again.reason)
        assert first.ticket_colours == again.ticket_colours
        assert first.colour in ("Red", "Amber", "Green")
