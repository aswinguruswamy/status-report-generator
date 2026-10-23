# Status Report Generator

[![CI](https://github.com/aswinguruswamy/status-report-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/aswinguruswamy/status-report-generator/actions/workflows/ci.yml)

A Python tool that reads Jira and writes a weekly status report. The report has a RAG status and a short AI summary.

> **Status:** In development (v1.0.0 planned for Oct 27, 2026).

## What it does

- Reads the tickets of one Jira project (read only).
- Calculates the weekly numbers: closed, opened, open, blocked, and overdue.
- Gives each open ticket a status: Black, Red, Amber, or Green.
- Shows a matrix of ticket status against priority (P1 to P5).
- Sets the project status (Red, Amber, or Green) with rules, not with AI.
- Uses the Claude API to write a short executive summary.
- Writes the report as Markdown and HTML.

## Setup

1. Install Python 3.11 or newer. The built-in Python on a Mac is too old.
2. Make a virtual environment: `python3.12 -m venv .venv`, then `source .venv/bin/activate`.
3. Run `pip install -r requirements.txt`, then `pip install -e .`.
4. Copy `.env.example` to `.env` and add your values.
5. Change `config.yaml` for your Jira project.

## Use

```
status-report                          # last full week, settings from config.yaml
status-report --week 2026-10-19        # the week that contains this day
status-report --project SRG --format both --no-ai
status-report --help                   # all options
```

The report goes into the `output` folder. Git ignores this folder. The file name has the
project key and the ISO week, for example `output/SRG-2026-W43.md`.

The Markdown report has these sections, in this order: project status, executive summary,
key numbers, priority matrix, blocked tickets, overdue tickets, closed this week, next week,
warnings, and all tickets. Each status is a colour mark and a word, for example "🔴 Red".
If the AI summary is not available, the summary and "Next week" sections say so.

**Caution:** Never commit the `.env` file. It contains your secrets.

## Tests

```
pytest                                  # all tests, no API calls (about 3 seconds)
python -m status_report.evaluation      # AI evaluation set: 5 real Claude API calls
```

- **Unit and scenario tests** check each status rule with a known result.
- **Random tests** make 300 difficult weeks with a fixed seed and check that the tool survives. A failing week is saved in `tests/regressions/` as a permanent test.
- **AI evaluation set** (`eval/samples/`) checks the quality of the AI summary: a red, an amber, a green, an empty week, and a week with hidden titles. Each sample lists facts that the summary must and must not contain. Run it after each change to the prompt or the model. It asks before it makes the calls.

## Limits

- Tested on Jira Cloud team-managed projects only.

## Project documents

Project documents: see `docs/` (added at v1.0.0). They are copies of the project's Confluence pages: charter, decisions, RAID log, status rules, and AI guardrails.

## License

MIT
