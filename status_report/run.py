"""One read of every team, shared by the command and the web page (spec SRG-R3.1, R13, R14)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from status_report.config import Config, ConfigError, load_config
from status_report.jira_client import JiraClient, ProjectNotFound
from status_report.portfolio import Portfolio, build_portfolio
from status_report.sources import read_teams


def load_settings(path: str | Path | None = None, demo: bool = False) -> Config:
    """The settings file: config.yaml, or demo/config.yaml in demo mode."""
    if path is None:
        from status_report.demo import CONFIG_FILE

        path = CONFIG_FILE if demo else "config.yaml"
        if demo and not CONFIG_FILE.is_file():
            raise ConfigError(
                "The sample data in demo/ was not found. Run the demo from a copy of the repository."
            )
    return load_config(path)


def make_client(demo: bool = False):
    """Demo mode: the recorded sample data, no token (R14.1). Else Jira with the .env values."""
    if demo:
        from status_report.demo import demo_client

        return demo_client()
    return JiraClient.from_env()  # No token: stops with the R13.3 message


def read_portfolio(client, config: Config, demo: bool = False, at_start: bool = False,
                   now: datetime | None = None) -> Portfolio:
    """Read every team and build the table.

    At start, a project that Jira does not know stops the tool (R13.2). On a later refresh
    it is one row "Could not read" (N4.1).
    """
    if now is None:
        if demo:
            from status_report.demo import demo_now

            now = demo_now()
        else:
            now = datetime.now(UTC)
    results = read_teams(client, config, now)
    if at_start:
        for team in config.teams:
            if isinstance(results[team.key], ProjectNotFound):
                raise results[team.key]
    return build_portfolio(config, results, now, sample=demo)
