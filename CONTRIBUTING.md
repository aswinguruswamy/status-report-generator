# Contributing to SRG

SRG is one of three PM tools (MCF, SRG, RAID) that share these rules. They come from the shared principles in [`specs/constitution.md`](specs/constitution.md).

## Before a change
1. **Spec first.** Each feature, rule or prompt change needs an approved spec with acceptance criteria. The approved specs are in [`specs/`](specs/); they are the source of truth.
2. **An approved spec is not edited silently.** Add a version line and a change-log row, and get the owner's approval.

## While you change
3. **Write the test first**, then the code.
4. **Every bug gets a test first** that shows the bug. For AI behaviour, also add a sample (eval case).
5. **Code writes the facts.** Numbers, dates, owners and colours come from code. The AI may choose or phrase, but it never invents a fact.
6. **No secrets in Git.** Keys and tokens live only in a local `.env` file or in GitHub repository secrets.
7. **Plain language.** Error messages say what happened and what to do.

## Before a merge
8. **CI must pass:** tests, lint, secret scan, dependency and licence scans. Branch protection enforces this.
9. Each pull request names the spec item it implements and gets an independent review.
10. Update the README "Known limits" when a limit changes.
