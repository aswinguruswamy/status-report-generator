"""Connection check: python -m status_report.check_jira

Reads the tickets of the last 7 days and prints a short summary.
It prints no token and changes nothing in Jira.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from status_report.config import ConfigError, load_config
from status_report.jira_client import JiraClient, JiraError


def main() -> int:
    try:
        config = load_config()
        client = JiraClient.from_env()
        user = client.connect()
        end = datetime.now(ZoneInfo(config.timezone)).date()
        start = end - timedelta(days=6)
        tickets = client.fetch_tickets(
            config.project_key,
            config.work_types,
            start,
            end,
            need_flag="flag" in config.blocked_methods,
        )
    except (ConfigError, JiraError) as error:
        print(f"ERROR: {error}")
        return 1

    print(f"Connected as: {user}")
    print(f"Address used: {client.api_url}")
    print(f"Project {config.project_key}, {start} to {end}: {len(tickets)} tickets")
    for ticket in tickets[:5]:
        print(f"  {ticket.key}  {ticket.status:<12} {ticket.priority or '-':<8} {ticket.title[:50]}")
    if len(tickets) > 5:
        print(f"  ... and {len(tickets) - 5} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
