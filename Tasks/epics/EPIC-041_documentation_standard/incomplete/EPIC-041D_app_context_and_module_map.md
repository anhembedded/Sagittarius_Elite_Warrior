# EPIC-041D — `Docs/ARCHITECTURE/context.md` and `module-map.md` describe the system in PlantUML, and module contracts are written once

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟡 — moderate; a checker or a rule changes and can turn CI red across the tree
**Complexity:** M — merges HLD 02/03 and SDD 05
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041B](EPIC-041B_doc_rule_links_checked_both_ways.md)

---

## 1. Context and problem
- Module contracts are written twice, in `Docs/HLD/03_module_contracts.md` and `Docs/SDD/05_module_contracts.md`.
- The context map (`Docs/HLD/02_context_map.md`) predates the bots, operations and alerting modules' current shape.
- No C4 container view shows the desktop process, the headless host, the CLI, Binance and the data root together.

## 2. Acceptance criteria
- [ ] `Docs/ARCHITECTURE/context.md`: a C4 context and a container diagram in PlantUML, with a legend and a source line per element.
- [ ] `Docs/ARCHITECTURE/module-map.md`: every module, its layer, its published contracts, and the allowed dependency directions, each direction citing the guard that enforces it (`test_module_boundaries.py`, `test_module_layers_point_inward.py`, `test_no_module_depends_on_operations.py`) and the rule clause that states it.
- [ ] Module contracts exist in one place only; the duplicate sections in HLD 03 and SDD 05 are replaced by a link and marked `Superseded by`.
- [ ] The checker from 041B passes on both files; the `Why:` lines of `architecture-rule.md` are repointed here.

## 3. Design
App docs summarise and link; detail lives in module docs and code (D3). PlantUML, as the owner decided, in `Docs/ARCHITECTURE/diagrams/`. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Content: `Docs/HLD/02_context_map.md`, `03_module_contracts.md`, `Docs/SDD/05_module_contracts.md`.
- Diagram style: `Docs/HLD/diagrams/hld-01b_module_dependencies.puml`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/ARCHITECTURE/context.md`, `module-map.md`, `diagrams/*.puml` | New |
| `Docs/HLD/03_module_contracts.md`, `Docs/SDD/05_module_contracts.md` | Replaced by a link |
| `.claude/rules/architecture-rule.md` | `Why:` lines repointed |

## 5. Testing
Documentation-only for the docs; the PlantUML files syntax-checked with the PlantUML version `Docs/SDD/README.md` names. A grep shows one definition of each module's contracts. Kind of pull request: doc.

## Implementation notes (written when done)
