"""Command line: status-report --project SRG --week 2026-10-19 (SRG-18).

Exit codes: 0 = report made, 1 = the tool stopped with an error, 2 = wrong options.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from status_report.config import ConfigError, load_config
from status_report.jira_client import JiraClient, JiraError
from status_report.report import write_report

EXIT_OK = 0
EXIT_ERROR = 1
FORMATS = {"md": ("markdown",), "html": ("html",), "both": ("markdown", "html")}


def week_range(day: date) -> tuple[date, date]:
    """Return Monday and Sunday of the week that contains the day."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def last_full_week(today: date) -> tuple[date, date]:
    """Return Monday and Sunday of the last full week before today."""
    return week_range(today - timedelta(days=7))


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="status-report",
        description="Read one Jira project and write a weekly status report.",
    )
    parser.add_argument("--project", help="Jira project key, for example SRG. Default: config.yaml.")
    parser.add_argument(
        "--week",
        type=date.fromisoformat,
        metavar="YYYY-MM-DD",
        help="Any day in the week to report (Monday to Sunday). Default: the last full week.",
    )
    parser.add_argument("--output", help="Folder for the report. Default: config.yaml.")
    parser.add_argument(
        "--format",
        choices=sorted(FORMATS),
        help="Report format: md, html, or both. Default: config.yaml.",
    )
    parser.add_argument("--no-ai", action="store_true", help="Make the report without the AI summary.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, client: JiraClient | None = None, today: date | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        project = args.project or config.project_key
        if today is None:
            today = datetime.now(ZoneInfo(config.timezone)).date()
        start, end = week_range(args.week) if args.week else last_full_week(today)
        formats = FORMATS[args.format] if args.format else config.output_formats
        folder = Path(args.output or config.output_folder)

        print(f"Project {project}, week {start} to {end}")
        print("1/3 Connecting to Jira...")
        client = client or JiraClient.from_env()
        client.connect()

        print("2/3 Reading tickets...")
        tickets = client.fetch_tickets(
            project, config.work_types, start, end, need_flag="flag" in config.blocked_methods
        )
        print(f"    {len(tickets)} tickets read")

        use_ai = config.ai_enabled and not args.no_ai
        print(f"    AI summary: {'on' if use_ai else 'off'}")

        print("3/3 Writing the report...")
        paths = write_report(tickets, project, start, end, folder, formats)
    except (ConfigError, JiraError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_ERROR

    for path in paths:
        print(f"Report: {path.resolve()}")
    return EXIT_OK
