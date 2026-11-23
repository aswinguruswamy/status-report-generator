"""Command line: status-report (spec SRG-R12; plan S8).

Reads every team in the settings file and writes the Markdown report.
Exit codes: 0 = report made, 1 = the tool stopped with an error, 2 = wrong options.
"""

from __future__ import annotations

import argparse
import sys

from status_report.config import ConfigError
from status_report.jira_client import JiraError
from status_report.report import marked, write_report
from status_report.run import load_settings, make_client, read_portfolio

EXIT_OK = 0
EXIT_ERROR = 1


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="status-report",
        description="Read every team in the settings file from Jira and write the team status report.",
    )
    parser.add_argument("--config", help="Path to the settings file. Default: config.yaml.")
    parser.add_argument("--output", help="Folder for the report. Default: output_folder in settings.")
    parser.add_argument("--demo", action="store_true",
                        help="Use the sample data in demo/. No Jira account or token is needed.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, client=None, now=None) -> int:
    args = parse_args(argv)
    try:
        config = load_settings(args.config, demo=args.demo)
        client = client or make_client(args.demo)
        print(f"Reading {len(config.teams)} teams{' (sample data)' if args.demo else ''}...")
        portfolio = read_portfolio(client, config, demo=args.demo, at_start=True, now=now)
        path = write_report(portfolio, args.output or config.output_folder)
    except (ConfigError, JiraError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_ERROR

    print(f"Team status {portfolio.as_of}")
    width = max(len(row.name) for row in portfolio.rows)
    for row in portfolio.rows:
        print(f"  {row.name:<{width}}  {marked(row.colour):<15} {row.progress:<22} {row.reason}")
    for warning in portfolio.warnings:
        print(f"WARNING: {warning}")
    print(f"Report: {path.resolve()}")
    return EXIT_OK
