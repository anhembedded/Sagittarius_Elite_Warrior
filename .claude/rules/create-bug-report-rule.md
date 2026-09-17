---
description: Create and maintain bug reports — unique IDs, observed evidence, honest unknowns, Bug Board entries and closure after verified fixes.
paths:
  - "Tasks/bug_report/**/*.md"
  - ".claude/templates/bug-report.md"
---

# Create and maintain a bug report

This rule owns the bug record and its board lifecycle. `fix-bug-rule.md` owns diagnosis, implementation and proof of a fix. A reporting-only request does not authorise implementation; an existing request to fix needs no second approval merely because the report is now filed. `[eye]`

## 1. Find or create the record

Check existing reports and the Bug Board for the same defect before creating a duplicate. For a new defect, take the next number after the highest BUG ID across both `Tasks/bug_report/incomplete/` and `Tasks/bug_report/completed/`, using files on disk rather than board counts. Create `Tasks/bug_report/incomplete/BUG-{nnn}_{slug}.md` from `.claude/templates/bug-report.md`. `[guard: test_task_board_is_consistent.py; review: K2]`

## 2. Capture what is known

Record when and where it was reported, severity with user impact, status Open, environment, expected versus actual behavior, reproduction steps and the available log/traceback/screenshot evidence. Read supplied evidence before describing it; exclude credentials and secrets. Distinguish an observed fact from a suspected cause. `[eye]`

A new report may say Unknown, Not yet reproduced, Not yet established or Not run. Root cause, Fix, Regression test and Verification can remain explicitly pending. Do not invent a cause or successful check to fill the template, and do not require a fix before recording a real symptom. Suggested next steps apply while Open. `[eye]`

## 3. Make the report visible

Add or update its linked row in `Tasks/bug_report/README.md`, the Bug Board. Keep report status and board state consistent. Follow ONBOARDING §6 for applicable roadmap bookkeeping; do not count bug reports as BOT tasks. `[guard: test_task_board_is_consistent.py; review: K2]`

## 4. Update and close

When diagnosis or implementation is authorised, follow `fix-bug-rule.md` and bring its established cause, changes, regression evidence and verification into this same report. Link a case study when that rule requires one. Keep the report Open while required fix verification is incomplete. `[review: K2]`

Only after the fix meets its verification requirements, move the report to `completed/` (`git mv` for a tracked file), set Fixed with the date and move its Bug Board row. Complete ONBOARDING §6's bookkeeping. This record transition does not itself claim the fix was committed, pushed or merged; state delivery truthfully in the user report. `[guard: test_task_board_is_consistent.py; review: K2]`
