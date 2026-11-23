# Changelog

## Unreleased (v2.0.0)

SRG v2 (spec `specs/spec.md` v1.3).

- S1: The AI summary is removed: `ai.py`, `evaluation.py`, `eval/`, the `ai:` settings and the `anthropic` package (spec §2 non-goals).
- S2: Settings v2: a `teams:` list (project key + team name); each v1 setting is optional with its v1 default; `timezone` defaults to the computer; new `forecast` setting. Clear start-up errors for no teams, a duplicate project, an unknown project, no token and a rejected token (SRG-R13.1–R13.3).
- S3: Jira reads for v2: active sprints (board → active sprints), the next release (fix version), the first closed ticket; teams read 4 at a time; a failed team does not stop the others. Recorded sample data for 4 made-up teams in `demo/` (`scripts/make_demo.py`).
- S4: Spec §4 definitions in code: counted, cleaned up, done, open, the 14-day window (local time), effective due date, overdue, blocked, not started, colour scope (sprint or last 14 days) and done/total.
- S5: Colours: ticket colour with "no date + high priority = Amber" (Black, Red, Amber, Green; first rule wins); the v1 team rule on the colour scope; the reason text with count, priority level, cause and up to 3 keys; unknown priorities are not high and give a warning.

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
