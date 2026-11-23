# Changelog

## Unreleased (v2.0.0)

<!-- At the release: change the heading above to "## v2.0.0 (<date>)" and set the version in
pyproject.toml to 2.0.0. The release workflow publishes this section as the release notes. -->

SRG v2: one table for every team, a report on demand, and no AI (spec `specs/spec.md` v1.3).
Public demo with made-up data: https://srg-app.streamlit.app

### Stories in this release

- S1: The AI summary is removed: `ai.py`, `evaluation.py`, `eval/`, the `ai:` settings and the `anthropic` package (spec §2 non-goals).
- S2: Settings v2: a `teams:` list (project key + team name); each v1 setting is optional with its v1 default; `timezone` defaults to the computer; new `forecast` setting. Clear start-up errors for no teams, a duplicate project, an unknown project, no token and a rejected token (SRG-R13.1–R13.3).
- S3: Jira reads for v2: active sprints (board → active sprints), the next release (fix version), the first closed ticket; teams read 4 at a time; a failed team does not stop the others. Recorded sample data for 4 made-up teams in `demo/` (`scripts/make_demo.py`).
- S4: Spec §4 definitions in code: counted, cleaned up, done, open, the 14-day window (local time), effective due date, overdue, blocked, not started, colour scope (sprint or last 14 days) and done/total.
- S5: Colours: ticket colour with "no date + high priority = Amber" (Black, Red, Amber, Green; first rule wins); the v1 team rule on the colour scope; the reason text with count, priority level, cause and up to 3 keys; unknown priorities are not high and give a warning.
- S6: The team table (`portfolio.py`): one row for each team with colour, reason, done/total ("3/5", "4/9 · 2 sprints", "1/4 · last 14 days"), % of open tickets with no due date, closed/opened in the last 14 days, the Black, Red and Amber tickets, and "Could not read – <reason>" for a team that fails. Sorted Red, Amber, Green, then name.
- S7: Forecast: the 85% date to finish all open counted tickets, from the MCF simulation (`mcf.forecast.api.forecast_from_counts`, fixed seed) on daily closed counts of the last 84 days; "Planned <date>" from the next release and "later than planned"; "Not enough history yet – needs 12 weeks" under 84 days of history. New dependency: `mcf` (pinned to an MCF commit).
- S8: The portfolio Markdown report `SRG_<yyyy-mm-dd>_<hhmm>.md` (as-of time, team table, reason per team, Black/Red/Amber tickets per team, "Sample data" in demo mode). `status-report` writes it (`--config`, `--output`, `--demo`). Removed: the v1 weekly report (Markdown and HTML), the weekly options and the v1 weekly code.
- S9: The web page (Streamlit): the team table with every colour as a word, "as of hh:mm", a team's Black/Red/Amber tickets on a row click (Jira links for real data), Refresh (a failed refresh shows the error and "Last good read hh:mm"), Generate report (download), and "Sample data" in demo mode. `demo_app.py` is the keyless public demo.

### Verified

- Every acceptance criterion of the spec has an automatic test, except the manual checks below.
- The demo data goes through the real Jira client, rules and report in the tests (offline).
- Each pull request had an independent review; CI runs the secret scan, style check, dependency
  and licence scans, and the tests on Python 3.11, 3.12 and 3.13.

### Known limits

- Tested on Jira Cloud **team-managed** projects only.
- One team = one Jira project. No programs, history or "what changed".
- The forecast needs 12 weeks (84 days) of history from the first closed ticket.
- Not yet checked by hand: 10 teams with real Jira in under 15 seconds (AC44) and a ticket link
  that opens Jira (AC42).

## v1.0.0 (2026-10-24)

The first release of the Weekly Status Report Generator.

### Stories in this release

**Jira connection**
- SRG-13: Read tickets from one Jira project for one week (read only, with the status history).
- SRG-17: Use the team's own names for priority, blocked, and work types (`config.yaml`).
- SRG-18: Run the tool from the command line (`status-report`).

**Status rules**
- SRG-19: Calculate the weekly numbers: closed, opened, open, blocked, overdue.
- SRG-20: Set the status of each ticket: Black, Red, Amber, Green.
- SRG-21: Set the project status from the priority matrix.
- SRG-22: Random generator, survival checks, and planned scenarios (300 seeds).

**AI summary**
- SRG-23: Write the executive summary from facts only, with answer checks.
- SRG-24: AI evaluation set (6 sample weeks; SRG-40 added the sample with quotes in the titles).
- SRG-25: Make the report without the AI (`--no-ai`, and when the AI fails).
- SRG-26: Option to hide ticket titles from the AI.

**Report output**
- SRG-27: Markdown report.
- SRG-28: HTML report (one file, phone and print friendly).

### Fixes from the sprint reviews
- SRG-34, SRG-38: The tool removes an AI summary that negates or softens the status.
- SRG-35: Text from Jira and the AI is safe in the Markdown report.
- SRG-36: The status reason names at most 3 tickets for each part.
- SRG-40: The AI answer uses structured outputs, so quotes in ticket titles cannot break it.
  Each warning states its reason.

### Engineering
- CI on each pull request: secret scan, style check, tests on Python 3.11, 3.12, and 3.13.
- GitHub Actions pinned to commit SHAs, with weekly Dependabot updates.
- Release workflow: a version tag runs the tests, builds the package, and publishes the GitHub
  release.

### Verified
- Real run against this Jira project: correct numbers, 4.5 seconds, AI summary done.
- AI evaluation set: 6 of 6. Tests: 609, on Python 3.11, 3.12, and 3.13.

### Known limits
- Tested on Jira Cloud team-managed projects only.
- One Jira project for each run.
- No Confluence, Slack, or GitHub Issues output (planned for v2).
- The flag and label methods for "blocked" use today's value, because Jira keeps no history
  for them.
