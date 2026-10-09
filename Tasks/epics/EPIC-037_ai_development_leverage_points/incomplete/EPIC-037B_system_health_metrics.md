# EPIC-037B — Bugs carry a root-cause class and the audit reports system-health metrics

**Status:** 🔵 Planned — not started
**Source:** the owner's systems-thinking review, 2026-10-09 (see the epic README for the quote)
**Risk:** 🟢 — template and audit changes; metrics can be gamed
**Complexity:** S — a template field, a rule clause, an audit section
**Epic:** [EPIC-037](../README.md)
**Depends on:** None

---

## 1. Context and problem
The goal the process optimises today is "this PR is green and the reviewer passed it" (leverage point 3). No measure shows whether the system is getting healthier: the fix share rose from 17.0% to 29.3% over ten weeks and nobody was told. The 2026-10-09 classification of 192 reports was done once by hand.

## 2. Acceptance criteria
- [ ] The bug template and `create-bug-report-rule.md` require a **Root-cause class** (A did not reuse · B forgiving double · C concurrency · D exchange semantics · E UI state · F persistence · G missing requirement · H other / test infra) and a **Found by** field (owner in real use · test · review · CI).
- [ ] `fix-bug-rule.md` §6.5 is extended: a class A fix adds a catalog row (037A) or a guard (037C); a class B fix hardens the fake or the double that missed it.
- [ ] The process-drift audit reports, every run: weekly `fix:` share, the class mix of bugs filed since the last run, the owner-found share, and the AI rule line count, each against the 2026-10-09 baseline in the epic README.
- [ ] The 192 existing reports keep their text; a one-off table of their classes (from the analysis) is stored in the epic folder, not written into each file.

## 3. Design
Leverage point 3 (goals) plus point 4 (self-organisation): every bug of class A or B leaves a mechanism behind. Read trends, never reward a number, so the prefix is not gamed.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/templates/bug_report.md` (or the current bug template), `.claude/rules/create-bug-report-rule.md` | two required fields |
| `.claude/rules/fix-bug-rule.md` | §6.5 extension |
| `.claude/skills/process-drift/SKILL.md` and its script | metrics section |
| `Tasks/epics/EPIC-037_ai_development_leverage_points/` | baseline class table |

## 5. Testing
Document guards and the reference checker; one dry run of the audit script on the current tree printing the four metrics.

## Implementation notes (written when done)
Not started.
