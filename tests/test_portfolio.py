"""The team table (spec SRG-R1, R2, R3.2, R9, R11, N4.1; plan S6)."""

from __future__ import annotations

from datetime import UTC, datetime

from v2_tickets import CONFIG, NOW, SPRINT, sprint, ticket

from status_report.config import Config, Team, load_config
from status_report.demo import CONFIG_FILE, demo_client, demo_now
from status_report.jira_client import JiraError
from status_report.models import TeamData
from status_report.portfolio import build_portfolio, build_row, percent
from status_report.sources import read_teams


def data(key, tickets, sprints=(SPRINT,), browse="https://site.example/browse/"):
    return TeamData(key, tuple(tickets), tuple(sprints), None, None, NOW, browse)


def row(tickets, sprints=(SPRINT,), key="BET", name="Beta"):
    return build_row(Team(key, name), data(key, tickets, sprints), CONFIG, NOW)


def green_sprint(n=1, prefix="BET"):
    return [ticket(f"{prefix}-{i}", due=9) for i in range(1, n + 1)]


# --- Rows and done/total (R1.1, R1.3, R2) ------------------------------------------------


def test_ac1_one_row_for_each_team_in_the_settings():
    results = {"ALP": data("ALP", green_sprint(prefix="ALP")), "BET": data("BET", green_sprint())}
    table = build_portfolio(CONFIG, results, NOW)
    assert [r.name for r in table.rows] == ["Alpha", "Beta"]
    assert all(r.colour and r.reason and r.progress for r in table.rows)


def test_ac2_progress_is_done_over_total():
    tickets = [ticket(f"BET-{n}", status="Done") for n in (1, 2, 3)] + green_sprint(2, "BET-X")
    assert row(tickets).progress == "3/5"


def test_ac4_no_sprint_label():
    created = [ticket(f"GAM-{n}", created=-n, sprints=()) for n in (1, 2, 3)]
    created.append(ticket("GAM-4", status="Done", created=-5, sprints=()))
    assert row(created, sprints=()).progress == "1/4 · last 14 days"


def test_ac31_two_sprints_count_together():
    s1, s2 = sprint(7, 3), sprint(8, 10)
    tickets = [ticket(f"BET-{n}", status="Done", sprints=(s1,)) for n in (1, 2, 3)]
    tickets += [ticket(f"BET-{n}", due=9, sprints=(s1,)) for n in (4, 5)]
    tickets += [ticket("BET-6", status="Done", sprints=(s2,))]
    tickets += [ticket(f"BET-{n}", due=9, sprints=(s2,)) for n in (7, 8, 9)]
    assert row(tickets, sprints=(s1, s2)).progress == "4/9 · 2 sprints"


def test_ac32_three_sprints():
    s1, s2, s3 = sprint(7, 3), sprint(8, 10), sprint(9, 5)
    tickets = [ticket("A-1", status="Done", sprints=(s1,)), ticket("A-2", due=9, sprints=(s1,)),
               ticket("A-3", status="Done", sprints=(s2,)), ticket("A-4", status="Done", sprints=(s2,)),
               ticket("A-5", due=9, sprints=(s2,)), ticket("A-6", due=9, sprints=(s3,))]
    assert row(tickets, sprints=(s1, s2, s3)).progress == "3/6 · 3 sprints"


def test_empty_project_is_0_of_0_green_with_no_percent_line():
    result = row([])
    assert result.progress == "0/0" and result.reason == "Green: No open tickets."
    assert result.no_due_text is None


# --- Sort (R1.2) -----------------------------------------------------------------------


def test_ac17_sort_by_colour_then_name():
    config = Config(teams=(Team("BET", "Beta"), Team("ALP", "Alpha"), Team("GAM", "Gamma")),
                    timezone=CONFIG.timezone)
    results = {
        "BET": data("BET", green_sprint()),
        "ALP": data("ALP", [ticket("ALP-1", priority="Highest", status="Blocked", due=9)]),
        "GAM": data("GAM", [ticket("GAM-1", priority="Low", status="Blocked", due=9)]),
    }
    table = build_portfolio(config, results, NOW)
    assert [(r.name, r.colour) for r in table.rows] == [
        ("Alpha", "Red"), ("Gamma", "Amber"), ("Beta", "Green")]


def test_same_colour_sorts_by_name_ignoring_case():
    config = Config(teams=(Team("B", "beta"), Team("A", "Alpha"), Team("C", "Charlie")),
                    timezone=CONFIG.timezone)
    results = {k: data(k, green_sprint(prefix=k)) for k in "ABC"}
    assert [r.name for r in build_portfolio(config, results, NOW).rows] == ["Alpha", "beta", "Charlie"]


# --- % with no due date (R9.1) -------------------------------------------------------------


def test_ac14_two_of_eight_open_tickets_have_no_due_date():
    tickets = [ticket(f"BET-{n}", due=9) for n in range(1, 7)]
    tickets += [ticket("BET-7", due=None), ticket("BET-8", due=None)]
    tickets += [ticket("BET-9", status="Done")]  # Not open: not in the count
    assert row(tickets).no_due_text == "25% of open tickets have no due date"


def test_ac15_one_of_three_is_33_percent():
    tickets = [ticket("BET-1", due=9), ticket("BET-2", due=9), ticket("BET-3", due=None)]
    assert row(tickets).no_due_text == "33% of open tickets have no due date"


def test_ac23_no_open_tickets_has_no_percent_line():
    result = row([ticket("BET-1", status="Done")])
    assert result.reason == "Green: No open tickets." and result.no_due_text is None


def test_percent_rounds_a_half_up():
    assert percent(1, 8) == 13 and percent(1, 3) == 33 and percent(2, 3) == 67
    assert percent(0, 5) == 0 and percent(5, 5) == 100


# --- Errors (N4.1) -------------------------------------------------------------------------


def test_ac29_one_team_fails_and_the_other_shows():
    results = {"ALP": data("ALP", green_sprint(prefix="ALP")),
               "BET": JiraError("Jira is busy or unavailable after 5 tries.")}
    table = build_portfolio(CONFIG, results, NOW)
    beta = next(r for r in table.rows if r.key == "BET")
    alpha = next(r for r in table.rows if r.key == "ALP")
    assert beta.colour is None
    assert beta.reason == "Could not read – Jira is busy or unavailable after 5 tries."
    assert alpha.colour == "Green"
    assert table.rows[0] is beta  # A failed team is shown first


# --- Details (R11.1, R11.2, R11.3) -----------------------------------------------------------


def test_ac33_problem_tickets_sorted_by_colour_priority_key_and_window_line():
    tickets = [
        ticket("BET-9", priority="Medium", due=1),  # Amber P3: shown in the details
        ticket("BET-2", priority="Highest", status="Blocked", due=9),
        ticket("BET-5", priority="High", status="Blocked", due=9),
        ticket("BET-1", priority="Low", due=9),  # Green: not in the details
        ticket("BET-20", created=-2, sprints=()),
    ]
    result = row(tickets)
    assert [p.key for p in result.problems] == ["BET-2", "BET-5", "BET-9"]
    assert [(p.colour, p.level, p.cause) for p in result.problems] == [
        ("Red", "P1", "Blocked"), ("Red", "P2", "Blocked"), ("Amber", "P3", "Due soon and not started")]
    assert result.window_text == "Closed 0 · Opened 1 in the last 14 days"


def test_details_order_black_first_then_priority_then_key():
    tickets = [ticket("BET-3", priority="Low", due=-1), ticket("BET-12", priority="High", due=-1),
               ticket("BET-4", priority="High", due=-1), ticket("BET-1", priority="Urgent", due=-1)]
    assert [p.key for p in row(tickets).problems] == ["BET-4", "BET-12", "BET-3", "BET-1"]


def test_each_key_links_to_jira_for_real_data_only():
    tickets = [ticket("BET-12", priority="Highest", status="Blocked", due=9)]
    assert row(tickets).problems[0].url == "https://site.example/browse/BET-12"
    sample = build_row(Team("BET", "Beta"), data("BET", tickets, browse=None), CONFIG, NOW)
    assert sample.problems[0].url is None


# --- As of (R3.2) and warnings (R13.4) -----------------------------------------------------


def test_as_of_is_local_time():
    table = build_portfolio(CONFIG, {"ALP": data("ALP", []), "BET": data("BET", [])},
                            datetime(2026, 12, 1, 14, 42, tzinfo=UTC))
    assert table.as_of == "as of 09:42" and table.read_date == "2026-12-01"


def test_ac41_warning_names_the_key_in_the_table():
    results = {"ALP": data("ALP", []),
               "BET": data("BET", [ticket("BET-3", priority="Urgent", due=9)])}
    table = build_portfolio(CONFIG, results, NOW)
    assert len(table.warnings) == 1 and "BET-3" in table.warnings[0]


# --- Demo end to end (plan SD2: the demo is also the offline test) ---------------------------


def test_demo_table():
    config = load_config(CONFIG_FILE)
    table = build_portfolio(config, read_teams(demo_client(), config, demo_now()), demo_now(),
                            sample=True)
    rows = {r.name: r for r in table.rows}
    assert [(r.name, r.colour) for r in table.rows] == [
        ("Alpha", "Red"), ("Beta", "Amber"), ("Delta", "Amber"), ("Gamma", "Green")]
    assert rows["Alpha"].reason.startswith("Red: 1 P1 ticket is blocked (ALP-")
    assert rows["Beta"].progress.endswith("· 2 sprints")
    assert rows["Gamma"].progress.endswith("· last 14 days")
    assert "closed" in rows["Delta"].reason and "opened" in rows["Delta"].reason
    assert "Urgent" in " ".join(table.warnings)
    assert table.as_of == "as of 09:42"
    assert all(p.url is None for r in table.rows for p in r.problems)


def test_as_of_on_a_utc_evening_that_is_another_local_day():  # S6 review
    late = datetime(2026, 7, 2, 2, 5, tzinfo=UTC)  # Summer time: 22:05 on 1 Jul in Toronto
    table = build_portfolio(CONFIG, {"ALP": data("ALP", []), "BET": data("BET", [])}, late)
    assert table.as_of == "as of 22:05" and table.read_date == "2026-07-01"


def test_error_without_text_and_ticket_without_priority():  # S6 review
    results = {"ALP": data("ALP", [ticket("ALP-1", priority=None, status="Blocked", due=9)]),
               "BET": JiraError("")}
    rows = {r.key: r for r in build_portfolio(CONFIG, results, NOW).rows}
    assert rows["BET"].reason == "Could not read – JiraError"
    assert (rows["ALP"].problems[0].priority, rows["ALP"].problems[0].level) == ("-", "Unmapped")
