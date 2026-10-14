# EPIC-041I — HLD, SDD and Diagrams keep only what is still unique, marked Historical, and the vocabulary is guarded

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟢 — low; documents and generated indexes
**Complexity:** S — moves, status lines and one guard
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041D](EPIC-041D_app_context_and_module_map.md), [EPIC-041E](EPIC-041E_bots_module_doc.md), [EPIC-041G](EPIC-041G_runtime_crosscutting_security_quality.md)

---

## 1. Context and problem
- Once 041D, 041E and 041G land, much of `Docs/HLD`, `Docs/SDD` and `Docs/Diagrams` repeats the new docs.
- `Docs/VOCABULARY/README.md` is cited by rules and skills but no guard checks it.

## 2. Acceptance criteria
- [ ] Every HLD, SDD and Diagrams section now covered elsewhere is replaced by a link and marked `Superseded by`; a section that is only history stays, marked `Historical`.
- [ ] Every rule and doc citation into a removed section is repointed; the 041B checker passes.
- [ ] A vocabulary guard: every term the vocabulary defines appears once, and every `Docs/VOCABULARY/README.md#anchor` cited in rules and docs resolves.
- [ ] `Docs/README.md` is updated to the final map.

## 3. Design
One fact, one place (D2), applied to the old trees last, once the new homes exist. Nothing is deleted that a decision record still cites; it is marked instead. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Anchor resolution: `scripts/rule_integrity/citations.py`.
- Index guard shape: `test_spec_index_is_consistent.py`.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `Docs/HLD/*`, `Docs/SDD/*`, `Docs/Diagrams/*` | Status lines and links |
| `Docs/README.md` | Final map |
| a vocabulary guard under `tests/unit/` | New |

## 5. Testing
The 041B checker on the whole tree; the vocabulary guard with a planted dangling anchor; a grep shows no section defined twice. Kind of pull request: doc + code.

## Implementation notes (written when done)
