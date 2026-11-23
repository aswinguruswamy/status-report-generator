"""Connection check: python -m status_report.check_jira

Reads every team in config.yaml and prints a short summary for each one.
It prints no token and changes nothing in Jira.
"""

from __future__ import annotations

import sys

from status_report.config import ConfigError
from status_report.jira_client import JiraError
from status_report.run import load_settings, make_client, read_portfolio


def main() -> int:
    try:
        config = load_settings()
        client = make_client()
        user = client.connect()
        portfolio = read_portfolio(client, config, at_start=True)
    except (ConfigError, JiraError) as error:
        print(f"ERROR: {error}")
        return 1
    print(f"Connected as: {user}")
    print(f"Address used: {client.api_url}")
    for row in portfolio.rows:
        print(f"  {row.key:<8} {row.name:<20} {row.progress:<22} {row.colour or row.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
