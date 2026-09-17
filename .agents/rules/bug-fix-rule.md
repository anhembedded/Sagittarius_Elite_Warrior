---
name: Bug Fix Rule
description: Root cause first, never a hotfix, log evidence, regression test before the fix at the right tier, kept forever, a report, and a case study when the gate was green.
trigger: always_on
---

# Bug fix workflow

## 1. Root cause first
Read the real evidence (traceback, log, screenshot) and the code it points at before writing a line. State the mechanism with `file:line` and why the fix resolves it without crossing a layer. When the gate was green while the defect was live, read `Docs/CASE_STUDIES/README.md` first — if the symptom rhymes with one, start from its "still open" list. `[review: E9]`

## 2. Never hotfix — fix the mechanism
A patch at the one call site the report surfaced, while the same defect can recur at every call site of that shape, is forbidden even when the symptom disappears. If the natural fix is "add the same timer/toggle/wiring to every Presenter", stop: move the mechanism to the one layer that serves every consumer (an application service publishing through the existing event pipeline, as `PositionRefreshService` replaced two per-screen timers in `BUG-117`). General over local, cost is never the reason (user decision 2026-09-08). A redesign stays bounded to the mechanism the bug lives in. `[review: E10]`

## 3. Prove reproduction and fix with logs
When reading is not conclusive, add temporary logging at **each** layer the failure could cross, reproduce, and capture the output as the evidence. After the fix, reproduce again and find **positive proof the new mechanism ran**, not just the absence of the symptom. Decide per line: promote to a permanent log under `logging-rule.md` (correct `"App.*"` name, level, tag), or discard; per-frame detail goes to `TRACE`. `[review: I5]`

## 4. Regression test first, confirmed red
Write the test before the fix and run it: it must fail **for the right reason**. Pick the tier where the crash lives — a `Mock` standing in for the crashing method cannot reproduce it (`BUG-013` "passed" twice with no fix). Then fix, then green, alongside §3's log. `[review: E9]`

## 5. Keep it forever
The regression test is never deleted, skipped, weakened or rewritten off the original failure path, unless replaced by stronger coverage of that exact path. `[review: E4]`

## 6. Commit
The fix and its regression test in one `fix:` commit whose body states the root cause and the id. `[review: L2]`

## 6.5 Case study when the gate was green
If an existing net (type checker, test, guard, review row) covered the area and missed it, and the same blind spot is open elsewhere now, add `Docs/CASE_STUDIES/CS-NNN_slug.md` in the fixing commit — one screen, the three sections the index requires — and **the check that closes it ships in the same commit**. Not every bug earns one. `[guard: test_case_study_index_is_consistent.py]`

## 7. Report
`Tasks/bug_report/incomplete/BUG-XXX_slug.md` (next number after the highest across both subdirectories, taken from disk): header (reported, severity, status), Symptom with real evidence, Root cause with `file:line`, Fix, Regression test (file; failed before, passes after). Filing before the fix is fine (`Status: Open`, suggested next steps). On fix: `git mv` to `completed/`, update status, move the row on the Bug Board (`Tasks/bug_report/README.md`) — the only place an open bug is visible. `[guard: test_task_board_is_consistent.py; review: K2]`
