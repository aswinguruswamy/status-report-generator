# Spec: SRG v2 – Team status table and report

Version: 1.3 | Status: **APPROVED by Aswin Guruswamy, 2026-11-22** (1.1 = consistency fix; 1.2 = his MCF trim decision; 1.3 = video) | Date: 2026-11-22
Tool: SRG | MoSCoW: Must (R4 forecast: Should) | Source: `specs/SRG/requirements.md` v1.3, `clarify/SRG-clarify-log.md`, SRG v1 code (`status.py`, `project.py`, `metrics.py`, `config.yaml`, read on 2026-11-22)

Requirement IDs `SRG-Rn` match R1–R14 and N1–N8 on the requirements page.
Sources: `R`/`N` = requirements page; `SRG-x.y` = SRG clarify log; `SH-x.y` = shared clarify log; `v1` = rule already in SRG v1 code; `proposal` = Claude's proposal, confirmed only by approval of this spec.

## 1. Problem
A PM with several teams in Jira must answer "how are the teams doing?" at any time. Today the PM waits for the weekly report or builds the answer by hand. Numbers are often old, and colours are often too kind.
SRG v1 reads one project per run, weekly, from the command line. It counts Won't Do and Duplicate tickets as finished work. A ticket with no due date can only be Red or Green, so a team without due dates looks Green.

## 2. Goal and non-goals
- **Goal:** one table that shows every team's status now, with the rule behind each colour, and a Markdown report on demand.
- **Non-goals:** AI text, sending the report, hosting, login, programs, history, colour override, per-team rule numbers (section 9).

## 3. Users and scenarios
| User | Scenario | Today | After |
|---|---|---|---|
| PM | Boss asks "how are the teams?" | Wait for the weekly report, or check each board | Open SRG, read the table in seconds |
| PM | Boss asks "why is Beta red?" | Open Jira and search | Click Beta: see the tickets and the rule |
| PM | Boss asks "will Beta make the date?" | Guess from the burndown | Planned date and forecast date side by side |
| PM | End of day update | Write it by hand | Click Generate report, share the Markdown file |
| Recruiter | Looks at the portfolio | Reads the README | Opens the public demo with sample data |

## 4. Definitions
All rules use these words with these meanings only.

| Term | Meaning | Source |
|---|---|---|
| Counted ticket | A Jira item whose type is in the `work_types` setting (default: Story, Task, Bug). Sub-tasks and epics are not counted. | v1, SRG-5.2 |
| Cleaned up | A ticket resolved as **Won't Do** or **Duplicate**. It is never done, opened, closed, open or in a total. | SRG-1.3, 2.16, R8 |
| Done | A counted ticket in the Done status category, not cleaned up. | v1, R8 |
| Open | A counted ticket not in the Done status category. A reopened ticket is open. | v1 |
| Closed in the window | A done ticket whose last move into Done is inside the window. A ticket that is reopened and closed again counts once. | v1 |
| Opened in the window | A counted ticket created inside the window, not cleaned up. | v1, SRG-2.16 |
| Window | The last 14 days: from 00:00 on (today − 13 days) to the read time. | SRG-2.19 |
| Today, local time | The date and time in the `timezone` setting (default: the computer's time zone). | v1, proposal |
| Effective due date | The ticket's due date; if none, the end date of its sprint; if none, no date. | SRG-2.18 |
| Overdue | Open, and effective due date before today. | v1 |
| Blocked | Open, and found by the `blocked_method` setting: status named `Blocked` (default), the Jira flag, or a label `blocked`. One or more methods. | v1, SRG-5.4 |
| High priority | Jira priority mapped to P1 or P2 in the `priority_map` setting (default: Highest = P1, High = P2). | v1, SRG-4.4 |
| Not started | Status category To Do. | v1 |
| Sprint scope | Counted tickets in the team's active sprint(s) at the read time. A ticket moved out of the sprint is not in scope. | SRG-3.2, 5.1 |
| No-sprint scope | For a team with no active sprint: counted tickets created, moved to another status, or closed inside the window. | SRG-3.2, 5.1 |
| Colour scope | Sprint scope; for a team with no active sprint, no-sprint scope. | SRG-5.1 |

## 5. Requirements (EARS)

### Team table
| ID | Type | Requirement | Source |
|---|---|---|---|
| SRG-R1.1 | Ubiquitous | The SRG shall show one row for each Jira project in the settings file, with the team name, team colour, colour reason and tickets done/total. | R1, SRG-3.1, 3.3 |
| SRG-R1.2 | Ubiquitous | The SRG shall sort rows by team colour (Red, Amber, Green), then by team name A–Z. | R1, SRG-4.2 |
| SRG-R1.3 | Ubiquitous | The SRG shall show done/total as: done tickets in the colour scope / all counted, not cleaned-up tickets in the colour scope. | R1, SRG-3.2 |
| SRG-R2.1 | State | While a team has no active sprint, the SRG shall use the no-sprint scope and label the cell "last 14 days". | R2, SRG-3.2 |
| SRG-R2.2 | State | While a team has more than one active sprint, the SRG shall count all active sprints together and label the cell "<n> sprints". | R1, proposal |
| SRG-R3.1 | Event | When the user opens the page or clicks Refresh, the SRG shall read Jira for every team. | R3, SRG-2.1 |
| SRG-R3.2 | Ubiquitous | The SRG shall show "as of hh:mm" in local time for the last good Jira read. | R3, N1 |
| SRG-R4.1 | Optional | Where the forecast is on, the SRG shall show the 85% date to finish all open counted tickets in the project, from the MCF simulation code with a fixed seed, using daily counts of closed tickets over the last 84 days (MCF method, MCF R6). | R4, SH-3.3, SRG-4.5 |
| SRG-R4.2 | Optional | Where the forecast is on and the project has a next release with a release date, the SRG shall show "Planned <date>" beside the forecast, and "later than planned" when the 85% date is after it. The forecast never changes the team colour. | R4, SRG-5.3 |
| SRG-R4.3 | Unwanted | If the project has fewer than 12 weeks (84 days) from its first closed ticket to today (both included), then the SRG shall show "Not enough history yet – needs 12 weeks" in place of the forecast. | R4, SRG-5.3, SRG-6.1 |

The **next release** is the unreleased Jira fix version with the earliest release date on or after today.

### Colours
| ID | Type | Requirement | Source |
|---|---|---|---|
| SRG-R5.1 | Ubiquitous | The SRG shall set every colour from rules in code. The only inputs are the Jira data, the settings and today's date. | R5, N2 |
| SRG-R6.1 | Ubiquitous | The SRG shall set each open ticket's colour; the first true rule wins: **Black** = overdue · **Red** = blocked · **Amber** = (effective due date within 2 days and not started) or (no effective due date and high priority) · **Green** = all other open tickets. | R6, R9, v1, SRG-2.18 |
| SRG-R7.1 | Ubiquitous | The SRG shall set the team colour from the tickets in the colour scope; the first true rule wins: **Red** = 1 or more high-priority tickets are Black or Red · **Amber** = 1 or more other tickets are Black or Red, or 1 or more high-priority tickets are Amber, or closed in the window < opened in the window (whole project) · **Green** = none of these. A team is never Black. | R5, R7, v1, SRG-5.5 |
| SRG-R8.1 | Ubiquitous | The SRG shall leave cleaned-up tickets out of every count, total and colour. | R8, SRG-1.3, 2.16 |
| SRG-R9.1 | Ubiquitous | The SRG shall show per team "<x>% of open tickets have no due date", from the open tickets in the colour scope, rounded to the nearest whole number. It shall not show the line when there are no open tickets. | R9, SRG-2.17 |
| SRG-R10.1 | Ubiquitous | The SRG shall show the reason beside each team colour, as in v1: "<Colour>: <part>; <part>." Each part names a count, a priority level, a cause and up to 3 ticket keys, then "and <n> more" (example: "Red: 1 P1 ticket is blocked (BET-12)."). Parts follow the R7.1 order. | R10, v1 |
| SRG-R10.2 | Ubiquitous | The SRG shall use "Green: No blocked, overdue, or at-risk tickets." for a Green team, and "Green: No open tickets." for a team with no open tickets. | R10, v1 |

### Details and report
| ID | Type | Requirement | Source |
|---|---|---|---|
| SRG-R11.1 | Event | When the user clicks a team row, the SRG shall show that team's Black, Red and Amber tickets (key, title, priority, colour, cause), sorted by colour (Black, Red, Amber), then priority (P1 first), then key. | R11 |
| SRG-R11.2 | Event | When the user clicks a team row, the SRG shall also show "Closed <n> · Opened <n> in the last 14 days". | R11, review finding 16 |
| SRG-R11.3 | Ubiquitous | The SRG shall link each ticket key to the ticket in Jira (real data only). | R11, proposal |
| SRG-R12.1 | Event | When the user clicks Generate report, the SRG shall create a Markdown file with the "as of" time, the team table, the reason per team, and each team's Black, Red and Amber tickets, from the same data as the page. | R12, SRG-2.26, 4.6 |
| SRG-R12.2 | Ubiquitous | The SRG shall name the report file `SRG_<yyyy-mm-dd>_<hhmm>.md`, with the read time. | R12, proposal |

### Setup and demo
| ID | Type | Requirement | Source |
|---|---|---|---|
| SRG-R13.1 | Ubiquitous | The SRG shall read one settings file: each Jira project key with its team name, plus the v1 settings with v1 defaults (`timezone`, `work_types`, `priority_map`, `blocked_method`, `blocked_status_name`, `blocked_label`, `amber_window_days`). No AI settings. | R13, SRG-5.4 |
| SRG-R13.2 | Unwanted | If, at start, the settings file is missing or empty, has a duplicate project key, or names a project that Jira does not know, then the SRG shall stop and show what is wrong and how to fix it. | R13, N7 |
| SRG-R13.3 | Unwanted | If, at start, the Jira token is missing or Jira rejects it, then the SRG shall stop and show how to set it. | N5, N7 |
| SRG-R13.4 | Unwanted | If a ticket has a priority that is not in `priority_map`, then the SRG shall treat it as not high priority and show a warning with the ticket key. | v1 |
| SRG-R14.1 | Optional | Where demo mode is on, the SRG shall use the sample data in the repo and need no Jira account or token. | R14 |
| SRG-R14.2 | State | While demo mode is on, the SRG shall show "Sample data" on the page and in the report. | R14, N4 |
| SRG-R15.1 | Ubiquitous | The README and the portfolio card shall link a video of 2 minutes or less that shows the team table, a team's details and the report. | R15, SH-4.4 |
| SRG-N4.1 | Unwanted | If, on a read after start, the SRG cannot read one team, then it shall show that row as "Could not read – <reason>" and show the other teams. | N4 |
| SRG-N4.2 | Unwanted | If a whole refresh fails, then the SRG shall show the error and "Last good read hh:mm", and shall not show the old data as new. | N4 |

## 6. Acceptance criteria
| ID | Given | When | Then | Test |
|---|---|---|---|---|
| AC1 | Settings list ALP (Alpha) and BET (Beta) | Page opens | 2 rows: Alpha, Beta | unit |
| AC2 | Active sprint: 5 counted tickets, 3 done | Table builds | "3/5" | unit |
| AC3 | Active sprint: 1 Won't Do + 4 counted tickets, 2 done | Table builds | "2/4" | unit |
| AC4 | No active sprint. In the window: 4 tickets created (1 of them closed); no other ticket changed | Table builds | "1/4 · last 14 days" | unit |
| AC5 | Open ticket, due yesterday | Ticket colour | Black | unit |
| AC6 | Open ticket, blocked, due in 10 days | Ticket colour | Red | unit |
| AC7 | Open ticket, due tomorrow, To Do | Ticket colour | Amber | unit |
| AC8 | Open ticket, due tomorrow, In Progress | Ticket colour | Green | unit |
| AC9 | Open ticket, no due date, sprint ended yesterday | Ticket colour | Black | unit |
| AC10 | Open ticket, no due date, no sprint, priority High | Ticket colour | Amber | unit |
| AC11 | Open ticket, no due date, no sprint, priority Medium | Ticket colour | Green | unit |
| AC12 | Open ticket, blocked, no due date, no sprint, priority High | Ticket colour | Red (blocked wins) | unit |
| AC13 | Project window: 10 opened (none cleaned up), 4 closed; 8 old tickets closed as Duplicate; all sprint tickets Green | Team colour | Amber; reason names "closed 4 and opened 10" | unit |
| AC14 | 2 of 8 open scope tickets have no due date | Table builds | "25% of open tickets have no due date" | unit |
| AC15 | 1 of 3 open scope tickets has no due date | Table builds | "33% …" | unit |
| AC16 | Same Jira data and settings, two runs | Colours, reasons, forecast | Same output | property |
| AC17 | Teams: Beta Green, Alpha Red, Gamma Amber | Table builds | Order: Alpha, Gamma, Beta | unit |
| AC18 | 1 High ticket overdue, others Green | Team colour | Red; "Red: 1 P2 ticket is overdue (BET-7)." | unit |
| AC19 | 1 Low ticket blocked, others Green, closed ≥ opened | Team colour | Amber | unit |
| AC20 | 1 Low ticket Amber, others Green, closed ≥ opened | Team colour | Green | unit |
| AC21 | 1 High ticket Amber, others Green | Team colour | Amber | unit |
| AC22 | 4 P1 tickets blocked: A-1…A-4 | Reason text | "Red: 4 P1 tickets are blocked (A-1, A-2, A-3, and 1 more)." | unit |
| AC23 | Sprint has no open tickets | Team colour | "Green: No open tickets."; no % line | unit |
| AC24 | Settings file empty | App starts | Stops: "The settings file has no teams. Add a project key and a team name." | unit |
| AC25 | Settings list ALP twice | App starts | Stops: "Project ALP is listed 2 times. Remove one." | unit |
| AC26 | Settings list XYZ, not in Jira | App starts | Stops: "Project XYZ not found in Jira. Check the key in settings." | unit (recorded response) |
| AC27 | No token in `.env`, demo off | App starts | Stops: "No Jira token found. Add JIRA_API_TOKEN to .env." | unit |
| AC28 | Jira rejects the token | App starts | Stops: "Jira did not accept the token. Make a new token and update .env." | unit (recorded response) |
| AC29 | Jira fails for BET only on Refresh | Table builds | ALP row OK; BET "Could not read – <reason>" | unit |
| AC30 | Last good read 09:00; whole refresh at 10:00 fails | Page shows | Error + "Last good read 09:00"; no "as of 10:00" | unit |
| AC31 | Active sprints 3/5 and 1/4 | Table builds | "4/9 · 2 sprints" | unit |
| AC32 | Active sprints 1/2, 2/3, 0/1 | Table builds | "3/6 · 3 sprints" | unit |
| AC33 | Beta has Amber P3 BET-9, Red P1 BET-2, Red P2 BET-5 | Row clicked | Order: BET-2, BET-5, BET-9; line "Closed n · Opened n" | unit |
| AC34 | Read at 09:42 on 2026-12-01 | Generate report | File `SRG_2026-12-01_0942.md`; content equals the page data | golden file |
| AC35 | Beta has 2 Red tickets | Generate report | Both listed under Beta | golden file |
| AC36 | Demo mode, no token | App starts | Sample teams show; "Sample data" on page and report | unit + manual |
| AC37 | Fixed seed; recorded 12 weeks of closed counts; 20 open tickets | Forecast | 85% date equals MCF output for the same input and seed | unit |
| AC38 | First closed ticket 82 days before today (83 days) | Forecast | "Not enough history yet – needs 12 weeks" | unit (edge) |
| AC38a | First closed ticket 83 days before today (84 days) | Forecast | Forecast shows | unit (edge) |
| AC39 | Next release dated 15 Dec; 85% date 9 Jan | Forecast | "Planned 15 Dec · Forecast 9 Jan · later than planned"; team colour unchanged | unit |
| AC40 | No unreleased fix version with a date | Forecast | Forecast date only | unit |
| AC41 | Ticket priority "Urgent", not in `priority_map` | Table builds | Treated as not high; warning names the key | unit |
| AC42 | Real data, Beta details open | Click BET-12 | Jira opens BET-12 | manual |
| AC43 | Demo mode | Page opens | Under 3 s on a standard laptop | manual (timed) |
| AC44 | 10 teams, real Jira | Refresh | Under 15 s | manual (before release) |
| AC45 | README | Docs test | Contains a video link (SRG-R15.1) | unit |

## 7. Non-functional requirements
| ID | Area | Requirement | Check |
|---|---|---|---|
| N1 | Freshness | Page and report show the Jira read time. | AC30, AC34 |
| N2 | Same result | Same data and settings → same colours, numbers, order and forecast (fixed seed). | AC16, AC37 |
| N3 | Speed | Demo opens < 3 s; refresh of 10 teams < 15 s. | AC43, AC44 |
| N4 | Honest errors | Failed reads are visible; no old data shown as new. | AC29, AC30 |
| N5 | Security | Real data runs locally; Jira token only in local `.env`; SRG only reads Jira (proposal). | secret scan in CI; review |
| N6 | Cost | No paid hosting; no AI calls. | review |
| N7 | Plain language | Errors say what happened and what to do. | AC24–AC28 |
| N8 | Proof | A test for every rule; "Known limits" in the README. | CI; review |
| N9 | Accessibility | Every colour also shows as a word (Red, Amber, Green, Black), never colour only (proposal). | AC17, manual |

## 8. Constitution check
| Principle | How this spec complies |
|---|---|
| P1 Code writes the facts | All numbers, colours and dates come from code. No AI in SRG v2. |
| P2 Verify before you show | Not applicable (no AI output). |
| P3 Fail loudly | SRG-R13.2, R13.3, R13.4, N4.1, N4.2. |
| P4 Time and source | "As of" time on page and report; "Sample data" label. No model or prompt (no AI). |
| P5 Least data to the AI | Not applicable (no AI). |
| P6 Secrets | Token only in local `.env`. |
| P7 Prove before you claim | Acceptance tests before the build; golden-file report tests. |
| P8 Same input, same output | SRG-R5.1, fixed forecast seed, AC16. |
| P9 One spec per change | This spec covers SRG v2. |
| P10 Simple first | Two jobs; v1 rules and settings reused. |
| P11 Plain language | N7. |
| P12 Quality gates | Shared CI standard (SH1). |

## 9. Edge cases
- Project with no tickets → "0/0", "Green: No open tickets.", no % line.
- Sprint where all tickets are cleaned up → "0/0".
- Ticket blocked and overdue → Black (R6.1 order).
- Ticket reopened after Done → open; if closed again in the window, it counts once.
- Ticket moved out of the sprint → not in sprint scope.
- Time zone → `timezone` setting.
- Jira rate limit or timeout → SRG-N4.1.
- Large project → read only the scope tickets, the window, and the closed history the forecast needs (check speed in the plan).
- There is no failure catalogue for SRG. This section is the list.

## 10. Out of scope
Sending the report (email, Slack, Teams) · AI summary · programs · history and "what changed" · colour override · per-team rule numbers · stuck-work and new-project rules · hosting and login · instant updates from Jira · RAID link · audience versions · Confluence page · a separate "cleaned up" line (dropped with requirements v0.2).

## 11. Clarify checklist
- [x] Actors and triggers – open page, Refresh, row click, Generate report
- [x] Inputs: format, size, missing data – settings, Jira, no due date, no sprint, unknown priority
- [x] Outputs – page and Markdown file; the PM shares it
- [x] Rules: every rule has a written source – section 4 and v1 code
- [x] Errors – R13.2, R13.3, R13.4, N4.1, N4.2
- [x] Edge cases – section 9
- [x] Data and privacy: what goes to the AI – nothing (no AI)
- [x] Freshness and time stamps – R3.2
- [x] Acceptance criteria testable – AC1–AC44
- [x] Dependencies on other specs – MCF simulation code; the exact function is a plan item
- [x] Cost and limits – N6

## 12. Answered questions
| Question | Answer | Log |
|---|---|---|
| Team colour rule | v1 priority rule (replaces "worst ticket wins") | SRG-5.5 |
| Black as a team colour | No | SRG-4.2 |
| Blocked | v1: `blocked_method` setting, default status "Blocked" | SRG-4.3, 5.4 |
| P1/P2 | Highest, High (v1 `priority_map` default) | SRG-4.4 |
| Forecast | All open tickets; min 12 weeks (was 5); planned date from the next Jira release | SRG-4.5, 5.3, 6.1 |
| Report contents | Table, reasons, Black/Red/Amber tickets per team | SRG-4.6 |
| Colour scope | Active sprint; no sprint → last 14 days | SRG-5.1 |
| Sub-tasks | Not counted | SRG-5.2 |
| Settings | Keep v1 settings with defaults | SRG-5.4 |

Still open (not for Aswin): the MCF function SRG calls – decide in the plan.

## Grades
### Independent review of v0.2 (separate session, 2026-11-22)
Completeness 🟡 · Testability 🟡 · Conflicts ❌ · Traceability 🟡. 3 blockers, 9 should-fix, 5 nits. v0.3 fixes all of them:
- blockers → section 4 definitions, R6.1 "blocked", colour scope;
- R8.1 and AC3, AC4, AC13 → definitions and new examples;
- forecast seed → R4.1;
- rule order → R6.1;
- start-up and refresh errors → R13.2, N4.1, N4.2;
- sources → corrected;
- reason text → R10.1, R10.2;
- missing ACs → AC23–AC32, AC38;
- nits → R2.2, R7.1 type, R9.1 rounding, R11.1 tie order, R11.2, N9, section 9.

### Builder pre-check of v0.3 (2026-11-22)
| Criterion | Grade | Evidence |
|---|---|---|
| Completeness | ✅ | Every page item maps to a row; all terms are defined (section 4); no open rule detail. |
| Testability | ✅ | AC1–AC44; 40 run as unit, property or golden tests. |
| Conflicts | ✅ | Team rule = v1 (SRG-5.5). Cleaned-up tickets are left out everywhere (R8.1). Scope is fixed per rule. |
| Traceability | ✅ | Each row has a source. Claude's own additions are marked "proposal": R2.2, R11.3, R12.2, N5 read-only, N9. |

Result: **pass (pre-check)**. Approved by Aswin on 2026-11-22.

## 13. Change log
| Version | Date | Change | Approved by |
|---|---|---|---|
| 0.1 | 2026-11-22 | First draft from requirements v1.0 | – |
| 0.2 | 2026-11-22 | 6 rule questions answered; AC29–AC31 added | – |
| 0.3 | 2026-11-22 | Independent review fixes; definitions; v1 team rule, blocked and settings; planned date; 5-week minimum; AC1–AC44 | – |
| 1.0 | 2026-11-22 | Approved as is, including the proposals R2.2, R11.3, R12.2, N5 read-only, N9 | Aswin Guruswamy |
| 1.1 | 2026-11-22 | Consistency fix, no scope change: R4.1 "weekly counts" → "daily counts" (the MCF method); short history depends on MCF R8 | Claude (admin fix, allowed by CLAUDE.md §5) |
| 1.3 | 2026-11-22 | Video (R15.1) | Aswin Guruswamy (SH-4.4) |
| 1.2 | 2026-11-22 | Forecast needs 12 weeks of history (was 5), because the MCF young-team rule is cut; R4.1 uses the MCF 84-day window | Aswin Guruswamy (MCF trim decision) |
