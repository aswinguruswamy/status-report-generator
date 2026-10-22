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

1. Install Python 3.11 or newer.
2. Run `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and add your values.
4. Change `config.yaml` for your Jira project.

**Caution:** Never commit the `.env` file. It contains your secrets.

## Limits

- Tested on Jira Cloud team-managed projects only.

## Project documents

The plan, decisions, and rules are in the Confluence space:
https://aswinguruswamy-1790217687632.atlassian.net/wiki/spaces/SRG/overview

## License

MIT
