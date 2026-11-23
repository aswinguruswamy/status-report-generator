# Constitution – MCF, SRG, RAID (v2)

Version: 1.1 – 2026-11-22. Status: **APPROVED by Aswin Guruswamy, 2026-11-22** (1.1 = his demo decision, SH-4.4). Owner: Aswin Guruswamy.
Every spec, plan and pull request must agree with these principles. A change to this file needs Aswin's approval and a new version line.

## Principles

**P1. Code writes the facts.** Numbers, dates, owners and colours come from code that reads the source data. The AI may choose, sort or phrase, but it never invents a fact. (Pattern from MCF: the AI picks approved sentences; code fills every number and date.)

**P2. Verify before you show.** Every AI output passes a code check before the user sees it. If the check cannot confirm a value, the tool shows "Not stated" or "Not confirmed" – never a guess.

**P3. Fail loudly.** A cut-off result is an error, not a warning. When part of a result is missing (example: one Jira project could not be read), the tool says so in the result. The user always knows what the tool did not do.

**P4. Every number has a time and a source.** Each output shows when the data was read and which data it used. Where AI is used, it also shows the model and the prompt version.

**P5. Least data to the AI.** Send only the fields the AI needs. No names, e-mails, descriptions or comments unless the feature needs them and the user sees a warning first.

**P6. Secrets never leave safe storage.** Keys and tokens live only in a local `.env` file or in GitHub repository secrets.

**P7. Prove before you claim.** Write the answer key before the test runs. Where the AI finds facts in text (RAID), keep a held-out set that is never used for tuning. Publish every score with its limits, also a score that misses its target.

**P8. Same input, same output.** Rules are written in config and code. A colour, a date or a forecast does not change between runs on the same data (forecasts use a fixed seed). Where AI output can vary between runs, the tool measures and publishes how much.

**P9. One spec per change.** No feature, rule or prompt change without an approved spec and acceptance criteria.

**P10. Simple first.** Build the smallest design that meets the spec. No speculative features. These are portfolio projects: judge each feature by its value to a real PM and to the public demo, at low cost. No paid hosting.

**P11. Plain language.** Docs, error messages and UI text use Simplified Technical English. Errors say what happened and what to do.

**P12. Quality gates.** Shared CI standard (tests, lint, secret scan, SHA-pinned actions, Dependabot, dependency audit, licence scan); independent review of every pull request; every bug gets a test and, for AI behaviour, an eval case before the fix.

## Shared items (SH1–SH11) – where each one lives

| ID | Shared item | Decision | Where |
|---|---|---|---|
| SH1 | Shared CI standard | Must | P12; RAID spec R17 (RAID is the weakest repo); MCF and SRG keep or reach the same standard |
| SH2 | Model and prompt version in every AI output | Must | P4; MCF spec R4; RAID spec R10 (SRG has no AI) |
| SH3 | AI test runs on each change to the prompt or model | Must | MCF spec R8; RAID spec R16 |
| SH4 | Every bug gets a test first | Must | P12; RAID spec R19 |
| SH5 | "Known limits" at the top of every README | Must | MCF spec R5; RAID spec R19; SRG spec N8 |
| SH6 | Release workflow (tag → tests → build → notes) | Must | RAID spec R18 (MCF and SRG have one) |
| SH7 | AI picks, code writes the facts | Must | P1 |
| SH8 | PM input | After release: 3–5 PMs try the demos (SH-4.2, replaces V6) | Phase 6 |
| SH9 | Tools feed each other | MCF → SRG: Must (MCF spec R6, SRG spec R4). RAID → SRG: later | |
| SH10 | Run inside Jira or Teams, or as an MCP server | Won't (v3) | |
| SH11 | Portfolio (multi-project) view | Must, as the SRG team table | SRG spec |
| SH12 | Public demos keyless + a recorded video per tool | Must (SH-4.4). The AI key is only a GitHub secret for the build and tests. | MCF R10–R11, SRG R15, RAID R20 |

## Governance
- Approver: Aswin. Proposer: Claude.
- Conflicts between a spec and this constitution: the constitution wins until Aswin changes it.
- Admin work that does not affect safety or security needs no approval (CLAUDE.md §5).

## Change log
| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-11-20 | Draft from SH1–SH7, robustness checks and the SRG-1 answers |
| 0.2 | 2026-11-22 | Checked against the approved specs: P3 covers a partial result (SRG); P4 model/prompt only where AI is used (SRG has none); P7 held-out set where AI finds facts (RAID), publish misses too; P8 fixed forecast seed and measured AI variation (RAID); P10 adds the portfolio-project rule (SH-3.1). Added the SH1–SH11 table. |
| 1.0 | 2026-11-22 | Approved as is by Aswin. SH8 row updated to his PM-input decision (SH-4.2). |
| 1.1 | 2026-11-22 | SH12 added: keyless demos + video per tool; AI key for the build only (Aswin, SH-4.4). |
