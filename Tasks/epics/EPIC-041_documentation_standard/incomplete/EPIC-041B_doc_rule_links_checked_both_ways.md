# EPIC-041B — Every architectural doc statement cites the rule clause that holds it, every such rule clause points back at its reason, and the checker fails when either side breaks

**Status:** 🔵 Backlog
**Source:** The owner, 2026-10-14: *"tui sắp chuẩn hóa doc … cho tôi cái triết lý doc, xem xem cái nào cần cái nào nên bỏ"* ("I am about to standardise the docs … give me a doc philosophy, what to keep and what to drop"); then *"doc phải liên kết với rule"* ("docs must be linked to the rules"), *"phải có phần doc để thống kê data … layer test nào phát hiện bao nhiêu bug, bao nhiêu bug người dùng phát hiện, giai đoạn nào"* ("there must be docs that collect data … which test layer found how many bugs, how many the user found, at which stage"), and *"tạo EPIC-041 ngay"* ("create EPIC-041 now")
**Risk:** 🟡 — moderate; a checker or a rule changes and can turn CI red across the tree
**Complexity:** M — extends `scripts/rule_integrity/` and edits five rules
**Epic:** [EPIC-041](../README.md)
**Depends on:** [EPIC-041A](../completed/EPIC-041A_docs_skeleton.md)

---

## 1. Context and problem
- Rules under `.claude/rules/` point into `Docs/` only for CASE_STUDIES, VOCABULARY and SPEC. No rule points at `Docs/HLD` or `Docs/SDD`, although `architecture-rule.md` is the law that design describes.
- 19 files under `Docs/` cite a rule; nothing checks that the cited clause exists.
- So the two drift apart silently, the failure `CONSTITUTION.md` P3 names.

## 2. Acceptance criteria
- [ ] `scripts/rule_integrity/trees.py` adds `Docs/ARCHITECTURE`, `Docs/MODULES`, `Docs/DECISIONS` and `Docs/METRICS` to the trees it checks.
- [ ] A new check: every doc→rule citation (`<rule>.md §N`) resolves to an existing section or numbered item.
- [ ] A new check: every `Why:` line in a rule resolves to an existing file and heading.
- [ ] A new check: every clause of `architecture-rule.md`, `async-ui-action-rule.md`, `domain-truth-rule.md`, `ui-presentation-rule.md` and `logging-rule.md` tagged `[gate]` or `[guard]` carries a `Why:` line, or appears in a shrink-only baseline.
- [ ] Probe tests: removing a cited heading, or renumbering a cited rule section, turns the checker red; the real tree is clean.
- [ ] `Why:` lines added to the five rules point at existing `Docs/HLD`, `Docs/SDD` or `DECISION_*` headings for now; 041D/041G repoint them as the new docs land.

## 3. Design
The doc/rule/guard triangle of decision D1. The checker already resolves `§` citations, quotes and paths inside the rule tree (`citations.py`, `quotes.py`, `paths.py`); this task widens the trees and adds the reverse direction, so no new tool is invented (P5). A `Why:` line must not break `tags.py` (every clause carries a tag) or `history.py` (no dates in rules): a `Why:` line is part of its clause, not a clause of its own. The philosophy every task follows is [DECISION_2026-10-14_documentation_philosophy.md](../DECISION_2026-10-14_documentation_philosophy.md).

## 3a. Reuse
- Checker: extended `scripts/rule_integrity/` (`trees.py`, `citations.py`, `markdown.py`).
- Test shape: mirrored `tests/unit/scripts/rule_integrity/` and `tests/unit/architecture/test_rule_tree_is_mechanically_consistent.py`.
- Shrink-only baseline: the existing `*_only_shrinks` pattern.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/rule_integrity/trees.py`, `citations.py`, a new `why_links.py` | The new trees and checks |
| `tests/unit/scripts/rule_integrity/test_why_links.py` | Probe tests |
| the five rules named above | `Why:` lines |

## 5. Testing
Unit tests with planted defects (red before, green after), the commit tier, and `python3 scripts/check_skill_prompt_references.py` on the real tree. Mutation check: remove the reverse check and see the probe go green wrongly. Kind of pull request: code.

## Implementation notes (written when done)
