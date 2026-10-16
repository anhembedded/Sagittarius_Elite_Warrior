# EPIC-041E — `Docs/MODULES/bots/` gives the bots module's design in the arc42 folder layout, with the lifecycle transition tables generated from the code

**Status:** ✅ Done (2026-10-16)
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟡 — moderate; a checker or a rule changes and can turn CI red across the tree
**Complexity:** M — one folder of nine documents and thirteen diagrams, one generator, one drift test
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041D](../incomplete/EPIC-041D_app_context_and_module_map.md) (for the module map only; started before it, on the coordinator's request of 2026-10-16, see Implementation notes); the folder layout of [EPIC-041J](../completed/EPIC-041J_module_folder_layout_and_design_in_step.md) ([decision of 2026-10-16](../DECISION_2026-10-16_module_docs_one_folder_arc42.md)), piloted on `Docs/MODULES/alerting/`

---

## 1. Context and problem
- The bots module (418 files, about 40,000 lines) has no module doc. Its design is spread over ADR 029, design 038 and design 039.
- The owner received an explanatory page on 2026-10-14 (context, components, state machine, four sequences, data model, threading, timing) and wants it in the repository.

## 2. Acceptance criteria
- [x] `Docs/MODULES/bots.md` moves to `Docs/MODULES/bots/` in the layout of `Docs/MODULES/README.md`: `README.md`, `03-context.md`, `05-building-blocks.md` (a hand-drawn component diagram and a class diagram of the domain and contracts only), `06-runtime.md` (four sequences: Start, a fill, Stop and Emergency Stop, restart → RECOVERING → Resume), `07-deployment.md` (threading and the headless host), `08-concepts.md` (the data model), `09-decisions.md`, `10-quality.md` (timing constants) and `state-machines.md` (the lifecycle and grid-level machines). Each cites code by path and symbol, never by line (`commit-rule.md` §1, "Citing code"; [decision of 2026-10-16](../DECISION_2026-10-16_cite_code_by_symbol.md)), so `test_module_docs_cite_code_by_symbol.py` stays green; every link to `bots.md` is fixed.
- [x] The two state machines' transition tables are generated from `src/modules/bots/domain/bot_lifecycle_fsm_matrix.py` and `domain/grid/grid_level_fsm_matrix.py` by a script; a test fails when the committed table differs from a fresh render. Architecture diagrams are drawn by hand at a high level (decision of 2026-10-16, D3).
- [x] The timing table is generated from the named constants, or tested against them.
- [x] Each view links up to `Docs/ARCHITECTURE/module-map.md` and to the rule clauses that hold it. *Delivered as:* the folder's `README.md` links up to `Docs/ARCHITECTURE/README.md`, the module map's home, because `module-map.md` is `EPIC-041D`'s and does not exist yet; `041D` retargets that one link when it writes the map (its criterion below). The views cite the rule clauses they encode (`architecture-rule.md` §3, `code/quality.md` §3, `commit-rule.md` §1).
- [x] A **Planned: EPIC-039L** section in `06-runtime.md` and in `state-machines.md` leaves the hook for the exchange-side protective stop, without designing it (the owner's instruction of 2026-10-16).

## 3. Design
Module doc = one arc42 folder at the component level (decision of 2026-10-16, D1–D3). Generated where the code is the source (D4); hand-written only for reasons and trade-offs. Design 038/039 and ADR 029 are linked, not copied. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Content: the coordinator's explanatory page of 2026-10-14 and its fact sheet.
- FSM tables: `bot_lifecycle_fsm_matrix.py`, `grid_level_fsm_matrix.py` (their `_TRANSITIONS` data).

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/MODULES/bots/` (the folder, its `diagrams/*.puml`); `Docs/MODULES/bots.md` deleted | New |
| `scripts/render_bots_design_tables.py` | New: the two transition tables and the timing table, between markers |
| `tests/unit/scripts/test_render_bots_design_tables.py` | Drift test, probes and generator tests |
| `Docs/MODULES/README.md`, `Tasks/epics/EPIC-040_backtest_workbench/README.md`, `EPIC-041D` | The link to the folder; the worked example of a generated table; the note to `040`'s children; the module-map link to retarget |

## 5. Testing
Unit tests for the generator; a drift probe that adds a transition to a copy of the table and sees the test fail; the 041B checker on the new doc. Kind of pull request: code.

## Implementation notes (written when done)
- Where the skeleton's views went: §1 → `03-context.md`; §2 → `05-building-blocks.md`; §3 → `state-machines.md`; §4 → `06-runtime.md`, split into five journeys (Start, a fill, Stop, Emergency Stop, restart and Resume): the task's "Stop and Emergency Stop" are two journeys, so two pictures (the owner's rule); §5 → `08-concepts.md`; §6 → `07-deployment.md`, with the headless host's shutdown policies (design 038 §6); §7 → `10-quality.md`, with a table of the scenarios that must hold. `04-solution-strategy.md`, `01`, `02` and `11` are left out (nothing to say yet, D7).
- Thirteen diagrams, each answering one question stated in its first line, none over seven boxes or participants; every one passes `plantuml -checkonly`. The lifecycle has nine states, so it is not drawn: its generated table is the picture.
- The generator is named for what it renders (`render_bots_design_tables.py`), not `render_fsm_diagrams.py` as §4 first said: it renders tables, and the timing table too. It reads each timing value from the code (a dataclass's field default, a module constant), so a changed constant fails the drift test and a renamed one fails at import.
- The facts carried from `bots.md` keep the citations `EPIC-041K` checked against the code at `30a75f9`; at `0353b16` the guard confirms every cited path and symbol still exists. The statements new in this folder were each read in the code before writing, among them: the Emergency Stop's path (`EmergencyStopCommandHandler` publishes the switch before it cancels; `GridFacts._apply_switch` halts `STARTING`, `RUNNING` and `PAUSED`, and leaves `STOPPING` waiting) and ADR 035's Phase 1 (`035A`–`035C`).
- Started before `041D`: the coordinator asked for this task once `EPIC-041K` merged. Only one criterion touches `041D`'s output, the up-link, handled as above.
- Verification evidence (commands and the CI run) is recorded on the pull request.
