# EPIC-041F — Every bug records where it was found and which nets it escaped, and a generated report answers which test layer catches what

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟡 — moderate; a checker or a rule changes and can turn CI red across the tree
**Complexity:** L — template, rule, guard, backfill, report generator, data dictionary
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041C](EPIC-041C_decisions_index.md)

---

## 1. Context and problem
- 213 bug reports exist, but only `Reported`, `Severity` and `Context` are fields, and they are free text. Which net caught a bug, which nets it escaped, the phase it was introduced and found in, and whether the owner or live trading found it are not recorded.
- `scripts/measure_process.py` counts files only. Case studies record the silent net for 8 bugs.
- Process decisions (another test tier, the 14-day soak, how reviews run) are taken without numbers.

## 2. Acceptance criteria
- [ ] `.claude/templates/bug-report.md` and `create-bug-report-rule.md` add structured fields: `Detected by`, `Introduced in`, `Phase introduced`, `Phase detected`, `Escaped nets`, `User-visible`, `Money at risk`, and the fix PR. The allowed values are the lists in decision D9.
- [ ] A guard fails when a bug report filed after this task lacks a field or uses a value outside its list.
- [ ] A backfill script fills the fields of existing reports that can be derived (dates, severity, reporter, the tier of the regression test) and writes `Unknown` for the rest. It never guesses; the report counts the unknowns.
- [ ] `scripts/render_quality_data.py` writes `Docs/METRICS/data/bugs.csv` and `Docs/METRICS/REPORT.md`: detection layer × severity, the share that reached the owner or real money, phase introduced → phase detected, time to fix, bugs per module. Output is deterministic.
- [ ] `Docs/METRICS/README.md` is the data dictionary: for each measure, the question, the definition, the source, the generator, the cadence and the feedback loop it feeds. It also lists the future data to start collecting (per-PR review rounds and findings, flaky reruns and surviving mutants, host RSS/fd/threads/restarts, bot halts and RECOVERING time, task lead time), each with where it will come from.
- [ ] The `process-drift` skill reads `REPORT.md` at each run.

## 3. Design
Decision D9. The fields are a closed vocabulary so the report can count them. Existing reports are backfilled once, by a script whose rules are in its docstring; manual correction afterwards is allowed and recorded in git. Each mandatory field is held by a rule clause and a guard (D1). The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Report shape: `scripts/measure_process.py` and `scripts/render_board.py`.
- Bug parsing: the board renderer already reads bug files.
- Escaped nets: `Docs/CASE_STUDIES/` records.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `.claude/templates/bug-report.md`, `.claude/rules/create-bug-report-rule.md` | New fields |
| `scripts/backfill_bug_fields.py`, `scripts/render_quality_data.py` | New |
| `Docs/METRICS/README.md`, `REPORT.md`, `data/bugs.csv` | New |
| `tests/unit/scripts/test_render_quality_data.py`, a bug-field guard | Tests |
| `.claude/skills/process-drift/SKILL.md` | Reads the report |

## 5. Testing
Unit tests on a `tmp_path` set of bug files (complete, partial, legacy); the guard's probe on a new bug without `Detected by`; a determinism test (two renders, same bytes); the backfill run on the real tree with its unknown counts recorded in Implementation notes. Kind of pull request: code.

## Implementation notes (written when done)
