"""The 85% forecast date for each team, from the MCF simulation code (spec SRG-R4; plan S7).

Input to MCF: daily counts of closed tickets (counted, not cleaned up) for the 84 days that
end today, and the number of open counted tickets in the whole project. MCF uses a fixed
seed, so the same data gives the same date (spec N2). The forecast never changes the team
colour (R4.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from mcf.forecast.api import forecast_from_counts
from mcf.forecast.montecarlo import MonteCarloError

from status_report.config import Config
from status_report.metrics import closed_at, is_counted, is_open_v2, local_today
from status_report.models import TeamData

HISTORY_DAYS = 84  # 12 weeks (spec R4.1, R4.3)
NOT_ENOUGH_HISTORY = "Not enough history yet – needs 12 weeks"
NO_OPEN_TICKETS = "No open tickets to forecast"
NO_CLOSED_TICKETS = "No forecast: no tickets closed in the last 12 weeks"


@dataclass(frozen=True)
class Forecast:
    text: str  # What the page and the report show
    mc85: date | None = None  # The 85% date
    planned: date | None = None  # Release date of the next release
    later: bool = False  # True when the 85% date is after the planned date


def short_date(day: date, today: date) -> str:
    """"15 Dec"; with the year when the date is not within the next 300 days."""
    text = f"{day.day} {day:%b}"
    if day < today or (day - today).days >= 300:
        text += f" {day.year}"
    return text


def daily_closed_counts(data: TeamData, config: Config, today: date) -> list[int]:
    """Closed tickets for each day of the 84 days that end today (local dates)."""
    zone = ZoneInfo(config.timezone)
    first = today - timedelta(days=HISTORY_DAYS - 1)
    counts = [0] * HISTORY_DAYS
    for ticket in data.tickets:
        if not is_counted(ticket, config):
            continue
        moment = closed_at(ticket)
        if moment is None:
            continue
        day = moment.astimezone(zone).date()
        if first <= day <= today:
            counts[(day - first).days] += 1
    return counts


def history_days(first_closed: datetime | None, today: date, timezone: str) -> int:
    """Days from the first closed ticket to today, both included (spec R4.3)."""
    if first_closed is None:
        return 0
    return (today - first_closed.astimezone(ZoneInfo(timezone)).date()).days + 1


def team_forecast(data: TeamData, config: Config, now: datetime) -> Forecast:
    today = local_today(now, config.timezone)
    planned = data.next_release.release_date if data.next_release else None
    if history_days(data.first_closed, today, config.timezone) < HISTORY_DAYS:
        return Forecast(NOT_ENOUGH_HISTORY, planned=planned)
    backlog = sum(1 for t in data.tickets if is_counted(t, config) and is_open_v2(t))
    if backlog == 0:
        return Forecast(NO_OPEN_TICKETS, planned=planned)
    try:
        result = forecast_from_counts(daily_closed_counts(data, config, today), today, backlog)
    except MonteCarloError:
        return Forecast(NO_CLOSED_TICKETS, planned=planned)
    mc85 = result.mc85
    if planned is None:
        return Forecast(f"Forecast {short_date(mc85, today)}", mc85)  # AC40
    later = mc85 > planned
    text = f"Planned {short_date(planned, today)} · Forecast {short_date(mc85, today)}"
    if later:
        text += " · later than planned"
    return Forecast(text, mc85, planned, later)
