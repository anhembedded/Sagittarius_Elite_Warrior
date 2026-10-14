# EPIC-041C — `Docs/DECISIONS/README.md` lists every decision, proposal and epic design, generated and guarded

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟢 — low; documents and generated indexes
**Complexity:** S — one generator and one guard
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041A](EPIC-041A_docs_map_and_status.md)

---

## 1. Context and problem
- 24 `DECISION_*.md` files live inside epic folders, 9 proposals under `Tasks/proposal/`, 5 `DESIGN_*.md` files under epics. "The ADR" cited across HLD/SDD is `EPIC-025/DECISION_2026-09-11_module_boundaries.md`.
- Nothing lists them; finding the decision behind a rule means knowing which epic took it.

## 2. Acceptance criteria
- [ ] `scripts/render_decisions_index.py` writes `Docs/DECISIONS/README.md`: one row per record with id, date, title, status, epic and link, newest first.
- [ ] A guard fails when the committed index differs from a fresh render, in the shape of `test_spec_index_is_consistent.py`.
- [ ] Records are never moved; the index links them where they are.
- [ ] New app-wide decisions may be written under `Docs/DECISIONS/` and appear in the same index.

## 3. Design
Generated, not hand-kept (D4). The status is read from each record's own `Status:` line; a record without one is listed as `Unknown`, never guessed. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Generator shape: `scripts/render_board.py` and its test.
- Guard shape: `tests/unit/architecture/test_spec_index_is_consistent.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/render_decisions_index.py` | New |
| `Docs/DECISIONS/README.md` | Generated |
| `tests/unit/scripts/test_render_decisions_index.py` | Generator and consistency tests |

## 5. Testing
Unit tests on a `tmp_path` tree (one record of each kind, one missing status); the consistency guard on the real tree; a probe that edits the index by hand and sees the guard fail. Kind of pull request: code.

## Implementation notes (written when done)
