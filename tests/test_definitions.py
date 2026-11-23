"""v2 definitions (spec §4, SRG-R1.3, SRG-R2.1, SRG-R8.1; plan S4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, time

from v2_tickets import CONFIG, NOW, SPRINT, TODAY, TZ, ZONE, at, move, sprint, ticket

from status_report.metrics import (
    closed_in_window,
    colour_scope,
    effective_due_date,
    is_blocked_v2,
    is_cleaned_up,
    is_counted,
    is_done_v2,
    is_not_started,
    is_open_v2,
    is_overdue_v2,
    local_today,
    opened_in_window,
    window_counts,
    window_start,
)

ACTIVE = {SPRINT.id}


# --- Counted, cleaned up, done, open ---------------------------------------------------


def test_counted_ticket_types_come_from_work_types():
    assert is_counted(ticket(work_type="Bug"), CONFIG)
    assert not is_counted(ticket(work_type="Sub-task"), CONFIG)
    assert not is_counted(ticket(work_type="Epic"), CONFIG)


def test_wont_do_and_duplicate_are_cleaned_up_not_done_and_not_open():
    for name in ("Won't Do", "Duplicate", "won’t do", " DUPLICATE "):
        t = ticket(status="Done", resolution=name)
        assert is_cleaned_up(t) and not is_done_v2(t) and not is_open_v2(t)
    done = ticket(status="Done")
    assert not is_cleaned_up(done) and is_done_v2(done) and not is_open_v2(done)


def test_reopened_ticket_is_open():
    history = [move(-5, "In Progress", "Done"), move(-2, "Done", "In Progress")]
    t = ticket(status="In Progress", history=history)
    assert is_open_v2(t) and not is_done_v2(t)


# --- Window and time zone ----------------------------------------------------------


def test_window_starts_at_midnight_13_days_before_today_local_time():
    assert window_start(NOW, TZ) == datetime(2026, 11, 18, 0, 0, tzinfo=ZONE)
    assert local_today(NOW, TZ) == TODAY


def test_today_uses_the_timezone_setting():
    late = datetime(2026, 12, 2, 3, 0, tzinfo=UTC)  # 22:00 on 1 Dec in Toronto
    assert local_today(late, TZ) == date(2026, 12, 1)
    assert local_today(late, "UTC") == date(2026, 12, 2)


def test_closed_in_window_edges():
    start = window_start(NOW, TZ)
    inside = ticket(status="Done", history=[move(-13, "In Progress", "Done", hour=0)])
    assert inside.history[0].at == datetime.combine(date(2026, 11, 18), time(0), ZONE)
    assert closed_in_window(inside, start, NOW)
    before = ticket(status="Done", history=[move(-14, "In Progress", "Done", hour=23)])
    assert not closed_in_window(before, start, NOW)


def test_reopened_and_closed_again_counts_once():
    history = [move(-10, "In Progress", "Done"), move(-8, "Done", "In Progress"),
               move(-3, "In Progress", "Done")]
    tickets = [ticket("BET-1", status="Done", history=history, created=-60)]
    assert window_counts(tickets, CONFIG, NOW) == (1, 0)


def test_cleaned_up_tickets_are_not_closed_or_opened():  # R8.1
    tickets = [ticket("BET-1", status="Done", resolution="Duplicate", created=-3),
               ticket("BET-2", status="Done", resolution="Won't Do", created=-60)]
    assert window_counts(tickets, CONFIG, NOW) == (0, 0)
    assert not opened_in_window(tickets[0], window_start(NOW, TZ), NOW)


def test_sub_tasks_are_not_counted_in_the_window():
    tickets = [ticket("BET-1", created=-2, work_type="Sub-task")]
    assert window_counts(tickets, CONFIG, NOW) == (0, 0)


# --- Effective due date, overdue, blocked, not started ---------------------------------


def test_effective_due_date_is_due_date_then_sprint_end_then_none():
    assert effective_due_date(ticket(due=3), TZ) == date(2026, 12, 4)
    assert effective_due_date(ticket(due=None), TZ) == date(2026, 12, 8)  # Sprint end
    assert effective_due_date(ticket(due=None, sprints=()), TZ) is None


def test_sprint_end_uses_the_active_sprint_then_the_latest():
    old, active = sprint(5, -7, "closed"), sprint(6, 7, "active")
    assert effective_due_date(ticket(sprints=(active, old)), TZ) == date(2026, 12, 8)
    older = sprint(4, -21, "closed")
    assert effective_due_date(ticket(sprints=(older, old)), TZ) == date(2026, 11, 24)


def test_sprint_end_date_is_the_local_date():
    from status_report.models import Sprint

    late = Sprint(8, "S8", "active", datetime(2026, 12, 9, 3, 0, tzinfo=UTC))
    assert effective_due_date(ticket(sprints=(late,)), TZ) == date(2026, 12, 8)


def test_overdue_is_open_with_effective_due_date_before_today():
    assert is_overdue_v2(ticket(due=-1), TODAY, TZ)
    assert not is_overdue_v2(ticket(due=0), TODAY, TZ)
    assert not is_overdue_v2(ticket(status="Done", due=-5), TODAY, TZ)
    ended = sprint(5, -1, "closed")
    assert is_overdue_v2(ticket(sprints=(ended,)), TODAY, TZ)  # Sprint ended yesterday


def test_blocked_by_each_method_and_only_when_open():
    assert is_blocked_v2(ticket(status="Blocked"), CONFIG)
    assert not is_blocked_v2(ticket(labels=("blocked",)), CONFIG)  # Default: status only
    both = replace(CONFIG, blocked_methods=("flag", "label"))
    assert is_blocked_v2(ticket(flagged=True), both)
    assert is_blocked_v2(ticket(labels=("Blocked",)), both)
    assert not is_blocked_v2(ticket(status="Done", labels=("blocked",)), both)


def test_not_started_is_status_category_to_do():
    assert is_not_started(ticket(status="To Do"))
    assert not is_not_started(ticket(status="In Progress"))
    assert not is_not_started(ticket(status="Blocked"))


# --- Colour scope and done/total (R1.3, R2.1) ---------------------------------------------


def test_ac2_sprint_with_5_tickets_3_done():
    tickets = [ticket(f"BET-{n}", status="Done") for n in range(1, 4)]
    tickets += [ticket("BET-4"), ticket("BET-5", status="In Progress")]
    scope = colour_scope(tickets, ACTIVE, CONFIG, NOW)
    assert (scope.done, scope.total, scope.sprints) == (3, 5, 1)


def test_ac3_wont_do_ticket_is_not_in_the_total():
    tickets = [ticket("BET-1", status="Done", resolution="Won't Do")]
    tickets += [ticket("BET-2", status="Done"), ticket("BET-3", status="Done"),
                ticket("BET-4"), ticket("BET-5")]
    scope = colour_scope(tickets, ACTIVE, CONFIG, NOW)
    assert (scope.done, scope.total) == (2, 4)


def test_ac4_no_active_sprint_uses_the_last_14_days():
    created = [ticket(f"GAM-{n}", created=-n, sprints=()) for n in range(1, 4)]
    created.append(ticket("GAM-4", status="Done", created=-5, closed=-1, sprints=()))
    unchanged = [ticket("GAM-9", created=-40, sprints=())]  # Old, no change in the window
    scope = colour_scope(created + unchanged, set(), CONFIG, NOW)
    assert (scope.done, scope.total, scope.sprints) == (1, 4, 0)


def test_no_sprint_scope_includes_tickets_moved_or_closed_in_the_window():
    moved = ticket("GAM-1", status="In Progress", created=-40, sprints=(),
                   history=[move(-3, "To Do", "In Progress")])
    closed = ticket("GAM-2", status="Done", created=-40, closed=-2, sprints=())
    moved_before = ticket("GAM-3", status="In Progress", created=-40, sprints=(),
                          history=[move(-20, "To Do", "In Progress")])
    scope = colour_scope([moved, closed, moved_before], set(), CONFIG, NOW)
    assert [t.key for t in scope.tickets] == ["GAM-1", "GAM-2"]


def test_ticket_moved_out_of_the_sprint_is_not_in_scope():
    out = ticket("BET-9", sprints=(sprint(5, -7, "closed"),))
    scope = colour_scope([ticket("BET-1"), out], ACTIVE, CONFIG, NOW)
    assert [t.key for t in scope.tickets] == ["BET-1"]


def test_several_active_sprints_count_together():
    second = sprint(8, 3)
    tickets = [ticket("BET-1", status="Done"), ticket("BET-2", sprints=(second,)),
               ticket("BET-3", sprints=(sprint(9, -14, "closed"),))]
    scope = colour_scope(tickets, {SPRINT.id, second.id}, CONFIG, NOW)
    assert (scope.done, scope.total, scope.sprints) == (1, 2, 2)


def test_sprint_with_only_cleaned_up_tickets_is_0_of_0():
    tickets = [ticket("BET-1", status="Done", resolution="Duplicate")]
    scope = colour_scope(tickets, ACTIVE, CONFIG, NOW)
    assert (scope.done, scope.total) == (0, 0)


def test_sub_tasks_are_not_in_scope():
    scope = colour_scope([ticket("BET-1", work_type="Sub-task")], ACTIVE, CONFIG, NOW)
    assert scope.total == 0


def test_window_counts_cover_the_whole_project_not_only_the_sprint():
    tickets = [ticket("BET-1", created=-2, sprints=()), ticket("BET-2", created=-3),
               ticket("BET-3", status="Done", created=-40, closed=-4, sprints=())]
    assert window_counts(tickets, CONFIG, NOW) == (1, 2)


def test_at_helper_is_local_time():
    assert at(0).tzinfo is ZONE


def test_done_ticket_without_history_uses_the_resolved_date():  # S4 review
    t = replace(ticket("BET-1", status="Done", history=[]), resolved=at(-2))
    assert closed_in_window(t, window_start(NOW, TZ), NOW)


def test_window_ends_at_the_read_time():  # S4 review
    later = ticket("BET-1", status="Done", history=[move(0, "In Progress", "Done", hour=11)])
    assert not closed_in_window(later, window_start(NOW, TZ), NOW)  # 11:00 is after 09:42
