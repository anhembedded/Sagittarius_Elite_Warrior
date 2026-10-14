# EPIC-041E — `Docs/MODULES/bots.md` gives the bots module's seven views, with the lifecycle diagram generated from the code

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟡 — moderate; a checker or a rule changes and can turn CI red across the tree
**Complexity:** M — one doc, one generator, one drift test
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041D](EPIC-041D_app_context_and_module_map.md)

---

## 1. Context and problem
- The bots module (418 files, about 40,000 lines) has no module doc. Its design is spread over ADR 029, design 038 and design 039.
- The owner received an explanatory page on 2026-10-14 (context, components, state machine, four sequences, data model, threading, timing) and wants it in the repository.

## 2. Acceptance criteria
- [ ] `Docs/MODULES/bots.md` holds the seven views: context, components, the lifecycle and grid-level state machines, four sequences (Start, a fill, Stop and Emergency Stop, restart → RECOVERING → Resume), the data model, threading and deployment, and timing constants. Each cites `file:line`.
- [ ] The two state-machine diagrams are generated from `src/modules/bots/domain/bot_lifecycle_fsm_matrix.py` and `domain/grid/grid_level_fsm_matrix.py` by a script; a test fails when the committed diagram differs from a fresh render.
- [ ] The timing table is generated from the named constants, or tested against them.
- [ ] Each view links up to `Docs/ARCHITECTURE/module-map.md` and to the rule clauses that hold it.

## 3. Design
Module doc = arc42 in small, at the component level (D3). Generated where the code is the source (D4); hand-written only for reasons and trade-offs. Design 038/039 and ADR 029 are linked, not copied. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Content: the coordinator's explanatory page of 2026-10-14 and its fact sheet.
- FSM tables: `bot_lifecycle_fsm_matrix.py`, `grid_level_fsm_matrix.py` (their `_TRANSITIONS` data).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/MODULES/bots.md`, `Docs/MODULES/diagrams/*.puml` | New |
| `scripts/render_fsm_diagrams.py` | New |
| `tests/unit/scripts/test_render_fsm_diagrams.py` | Drift test and generator tests |

## 5. Testing
Unit tests for the generator; a drift probe that adds a transition to a copy of the table and sees the test fail; the 041B checker on the new doc. Kind of pull request: code.

## Implementation notes (written when done)
