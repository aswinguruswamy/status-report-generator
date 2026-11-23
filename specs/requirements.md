# SRG v2 – Requirements

Version 1.3 · 2026-11-22 · Status: **APPROVED by Aswin Guruswamy, 2026-11-22** (v1.1–v1.3: changes from his later answers)

---

## 1. What SRG v2 is

A simple tool that shows **how every team stands right now**, from Jira.
One table: each team, its colour, and tickets done in the current sprint (example: **3/5**).
Click a team for details. Click **Generate report** to get a Markdown file. SRG stops there.

**Pick one line for the README and the demo** (or write your own):
1. "Every team's status, right now – and the PM rule behind every colour."
2. "Answer your boss in 10 seconds: one table, every team, honest colours."
3. "Team status from Jira, set by rules a PM would write."

## 2. Who uses it, and the problem

**User:** a PM, senior PM or program manager with several teams in Jira.

**Problem:** the boss asks "how are the teams doing?" The PM waits for the weekly report or builds the answer by hand. The numbers are often old, and the colours are often too kind.

## 3. How a PM uses it

1. **Open SRG.** It reads Jira for your teams. The page shows "as of 09:42".
2. **Scan the table.**

   | Team | Status | Sprint | Finish (85%) |
   |---|---|---|---|
   | Alpha | 🟢 Green | 3/5 | 28 Nov |
   | Beta | 🔴 Red – 2 blocked | 1/6 | 9 Dec |

3. **Click a team.** See the tickets behind the colour and the rule that set it.
4. **Click Generate report** – at end of day, or at any time. Download a Markdown file. Share it any way you like.

## 4. Benefits

| For | Benefit |
|---|---|
| The PM | Answer "how are the teams doing?" **in seconds**, at any time. |
| The PM | **Trust the colour**: written PM rules set it, the same way every time. |
| The boss | One table for all teams. Red teams first, with the reason. |
| The team | Fair colours: cancelled and duplicate tickets do not count against them. |
| Recruiters | A working public demo that shows **PM knowledge in code**: status rules, a forecast, data-quality checks. |

## 5. What it does (functional requirements)

Priority is my proposal. **You decide.** M = Must, S = Should.

### Team table
| # | Requirement | Priority |
|---|---|---|
| R1 | Show one row per team (one team = one Jira project), with its colour and tickets done/total in the current sprint. Red teams first. | M |
| R2 | For a team without sprints, count the last 14 days. | M |
| R3 | Read Jira each time you open the page or click Refresh. Show "as of hh:mm". | M |
| R4 | Show a forecast finish date per team (from the Monte Carlo forecast tool), beside the planned date of the team's next Jira release. Needs 12 weeks of history. | S |

### Colours (the PM rules)
| # | Requirement | Priority |
|---|---|---|
| R5 | Set every colour from written rules. Same data → same colour, every time. | M |
| R6 | Ticket colours: **Black** = overdue · **Red** = blocked · **Amber** = due within 2 days and not started · **Green** = on track. | M |
| R7 | A team turns Amber when it closed fewer tickets than it opened in the last 14 days. | M |
| R8 | Do not count Won't Do or Duplicate tickets as finished work. | M |
| R9 | A ticket with no due date uses the sprint end date. If there is none, a high-priority ticket (Highest, High) turns Amber. Show "x% of tickets have no due date". | M |
| R10 | Show the rule that set each colour, in plain words. | M |

### Details and report
| # | Requirement | Priority |
|---|---|---|
| R11 | Click a team to see the tickets behind its colour. | M |
| R12 | Generate a Markdown report for all teams (table + reasons), at any time. | M |

### Setup and demo
| # | Requirement | Priority |
|---|---|---|
| R13 | One settings file: the Jira projects and a team name for each, plus the v1 settings with their defaults (blocked method, priority names, ticket types, time zone). Check it at start; stop with a clear message if a value is wrong. | M |
| R14 | Public demo with sample data. No Jira account needed. | M |
| R15 | Record a short video (2 minutes or less) of the team table and the report; link it in the README and the portfolio. | M |

## 6. How well it must work (non-functional requirements)

| # | Area | Requirement |
|---|---|---|
| N1 | Freshness | The page and the report show when Jira was read. |
| N2 | Same result | The same Jira data always gives the same colours and numbers. |
| N3 | Speed | The demo opens in under 3 seconds. A refresh of 10 teams takes under 15 seconds. *(proposed numbers – confirm)* |
| N4 | Honest errors | If SRG cannot read a team, it says so. It never shows old data as new. |
| N5 | Security | Real Jira data runs only on the PM's own computer. The Jira token stays in a local secrets file. |
| N6 | Cost | Free to run. No paid hosting. No AI cost. |
| N7 | Plain language | Screens, errors and docs use simple English. Errors say what happened and what to do. |
| N8 | Proof | Automated tests for every rule. "Known limits" at the top of the README. |

## 7. Not in v2 (later, if SRG becomes popular)

- Send the report by email, Slack or Teams.
- AI summary in the report.
- Programs (groups of teams).
- What changed since yesterday (saved history).
- PM colour override.
- Different rule numbers per team.
- Stuck-work rule and new-project rule.
- Hosted version with login; instant updates from Jira.
- RAID risks and issues per team.

## 8. Sign-off

| | |
|---|---|
| Comments | None ("Approve as is") |
| Decision | ☑ Approved ☐ Approved with changes ☐ Rejected |
| Signed | Aswin Guruswamy · 2026-11-22 (in chat) |
| Note | Positioning line (section 1) not picked yet. Speed numbers N3 accepted as written. |

## Change log
| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-11-20 | First draft (25 requirements) |
| 0.2 | 2026-11-22 | Cut to 2 jobs: team table + report. Removed AI, programs, history, override, per-team settings, stuck-work and new-project rules. Added sprint count (3/5). 14 requirements. |
| 1.0 | 2026-11-22 | Approved as is by Aswin. No content change. |
| 1.1 | 2026-11-22 | From Aswin's answers in the spec review: team colour uses the v1 priority rule; planned date from the next Jira release beside the forecast; 5-week minimum; v1 settings kept; sub-tasks not counted. |
| 1.2 | 2026-11-22 | Forecast needs 12 weeks of history (was 5) – Aswin's MCF trim decision. |
| 1.3 | 2026-11-22 | Aswin: a recorded video beside the live demo (R15). |

Every line traces to Aswin's answers in `clarify/SRG-clarify-log.md`.
