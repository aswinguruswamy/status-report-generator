"""The forecast (spec SRG-R4.1–R4.3; AC37–AC40; plan S7)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from mcf.forecast.api import forecast_from_counts
from v2_tickets import CONFIG, NOW, TODAY, at, ticket

from status_report.config import Team, load_config
from status_report.demo import CONFIG_FILE, demo_client, demo_now
from status_report.forecast import (
    NO_CLOSED_TICKETS,
    NO_OPEN_TICKETS,
    NOT_ENOUGH_HISTORY,
    daily_closed_counts,
    short_date,
    team_forecast,
)
from status_report.models import Release, TeamData
from status_report.portfolio import build_portfolio, build_row
from status_report.sources import read_teams


def closed_every(days: int, step: int = 4, prefix: str = "BET"):
    """One closed ticket every `step` days, for the last `days` days."""
    return [ticket(f"{prefix}-{n}", status="Done", created=-days - 10, closed=-n, sprints=())
            for n in range(0, days, step)]


def open_tickets(count: int, start: int = 500):
    return [ticket(f"BET-{start + n}", sprints=(), due=30) for n in range(count)]


def team_data(tickets, first_closed_days=120, release=None):
    first = at(-first_closed_days) if first_closed_days is not None else None
    return TeamData("BET", tuple(tickets), (), release, first, NOW, None)


def test_ac37_85_percent_date_equals_mcf_for_the_same_input_and_seed():
    tickets = closed_every(84, step=3) + open_tickets(20)
    data = team_data(tickets)
    counts = daily_closed_counts(data, CONFIG, TODAY)
    assert len(counts) == 84 and sum(counts) == 28
    expected = forecast_from_counts(counts, TODAY, 20).mc85
    result = team_forecast(data, CONFIG, NOW)
    assert result.mc85 == expected
    assert team_forecast(data, CONFIG, NOW) == result  # Fixed seed: same result again


def test_ac38_83_days_of_history_is_not_enough():
    data = team_data(closed_every(80) + open_tickets(5), first_closed_days=82)
    assert team_forecast(data, CONFIG, NOW).text == NOT_ENOUGH_HISTORY
    assert NOT_ENOUGH_HISTORY == "Not enough history yet – needs 12 weeks"


def test_ac38a_84_days_of_history_shows_the_forecast():
    data = team_data(closed_every(80) + open_tickets(5), first_closed_days=83)
    result = team_forecast(data, CONFIG, NOW)
    assert result.mc85 is not None and result.text.startswith("Forecast ")


def test_no_closed_ticket_ever_is_not_enough_history():
    assert team_forecast(team_data(open_tickets(3), None), CONFIG, NOW).text == NOT_ENOUGH_HISTORY


def test_ac39_planned_date_and_later_than_planned():
    # Few closes and many open tickets: the 85% date is long after 15 Dec.
    data = team_data(closed_every(84, step=7) + open_tickets(12),
                     release=Release("2.4", date(2026, 12, 15)))
    result = team_forecast(data, CONFIG, NOW)
    assert result.later and result.planned == date(2026, 12, 15)
    assert result.text == f"Planned 15 Dec · Forecast {short_date(result.mc85, TODAY)} · later than planned"


def test_ac39_exact_text_for_9_jan():
    assert short_date(date(2026, 12, 15), TODAY) == "15 Dec"
    assert short_date(date(2027, 1, 9), TODAY) == "9 Jan"


def test_forecast_before_the_planned_date_has_no_warning():
    data = team_data(closed_every(84, step=1) + open_tickets(3),
                     release=Release("Spring", date(2027, 3, 1)))
    result = team_forecast(data, CONFIG, NOW)
    assert not result.later and "later than planned" not in result.text
    assert result.text.startswith("Planned 1 Mar · Forecast ")


def test_ac40_no_release_shows_the_forecast_date_only():
    data = team_data(closed_every(84) + open_tickets(5))
    result = team_forecast(data, CONFIG, NOW)
    assert result.text == f"Forecast {short_date(result.mc85, TODAY)}" and result.planned is None


def test_ac39_forecast_never_changes_the_team_colour():
    tickets = closed_every(84, step=7) + open_tickets(12)
    late = team_data(tickets, release=Release("2.4", date(2026, 12, 15)))
    on = build_row(Team("BET", "Beta"), late, CONFIG, NOW)
    off = build_row(Team("BET", "Beta"), late, replace(CONFIG, forecast=False), NOW)
    assert on.forecast.later and off.forecast is None
    assert (on.colour, on.reason) == (off.colour, off.reason)


def test_backlog_is_all_open_counted_tickets_of_the_project():
    tickets = closed_every(84) + open_tickets(4)
    tickets += [ticket("BET-900", work_type="Sub-task", sprints=()),  # Not counted
                ticket("BET-901", status="Done", resolution="Won't Do", sprints=())]
    data = team_data(tickets)
    expected = forecast_from_counts(daily_closed_counts(data, CONFIG, TODAY), TODAY, 4).mc85
    assert team_forecast(data, CONFIG, NOW).mc85 == expected


def test_daily_counts_leave_out_cleaned_up_and_old_tickets():
    tickets = [ticket("BET-1", status="Done", closed=0, sprints=()),
               ticket("BET-2", status="Done", closed=-83, sprints=()),
               ticket("BET-3", status="Done", closed=-84, sprints=()),  # Before the 84 days
               ticket("BET-4", status="Done", closed=-5, resolution="Duplicate", sprints=())]
    counts = daily_closed_counts(team_data(tickets), CONFIG, TODAY)
    assert counts[-1] == 1 and counts[0] == 1 and sum(counts) == 2


def test_no_open_tickets_and_no_recent_closes():
    assert team_forecast(team_data(closed_every(84)), CONFIG, NOW).text == NO_OPEN_TICKETS
    old = [ticket("BET-1", status="Done", closed=-100, sprints=())]
    assert team_forecast(team_data(old + open_tickets(2)), CONFIG, NOW).text == NO_CLOSED_TICKETS


def test_short_date_adds_the_year_far_away_or_in_the_past():
    assert short_date(TODAY + timedelta(days=400), TODAY) == "5 Jan 2028"
    assert short_date(date(2026, 11, 30), TODAY) == "30 Nov 2026"


def test_demo_forecasts():
    config = load_config(CONFIG_FILE)
    table = build_portfolio(config, read_teams(demo_client(), config, demo_now()), demo_now())
    rows = {r.name: r for r in table.rows}
    assert rows["Alpha"].forecast.planned == date(2026, 12, 15)
    assert rows["Alpha"].forecast.text.endswith("· later than planned")
    assert rows["Beta"].forecast.text.startswith("Planned 1 Mar · Forecast ")
    assert not rows["Beta"].forecast.later
    assert rows["Gamma"].forecast.text.startswith("Forecast ")  # Release without a date
    assert rows["Delta"].forecast.text == NOT_ENOUGH_HISTORY  # Young team
