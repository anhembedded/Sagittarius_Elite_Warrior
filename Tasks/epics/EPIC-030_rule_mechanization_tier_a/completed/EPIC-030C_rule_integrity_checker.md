# EPIC-030C — The rule tree checks itself: tags, targets, sections, quotations, history

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟡 — A false positive blocks every commit
**Complexity:** M — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030A, EPIC-030B merged

---

## 1. Context and problem
`scripts/check_skill_prompt_references.py` verified paths and review IDs only. Section anchors, quotations, guard targets, gate claims and clause tags were checked by nobody, which is how every finding of `EPIC-030A` and `EPIC-030B` accumulated (the 2026-09-16 strategic review's PCS-5, still open).

## 2. Acceptance criteria
- [x] `python3 scripts/check_skill_prompt_references.py` fails, with `file:line`, on an untagged clause, a missing or ambiguous guard, an unselected ruff gate, a missing section anchor, a malformed `§`, an out-of-range invariant, an invented quotation and a dated amendment.
- [x] It passes on `master-warrior` after PR 1, on Python 3.11 and 3.12.
- [x] A real-tree guard under `tests/unit/architecture` runs every check.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/rule_integrity/` | New package: paths, clause tags, tag grammar, § citations, quotes, invariant refs, history |
| `scripts/check_skill_prompt_references.py` | Thin entry point, same CLI contract |
| `tests/unit/scripts/rule_integrity/` | Planted-defect unit tests per check |
| `tests/unit/architecture/test_rule_tree_is_mechanically_consistent.py` | Real-tree guard in the commit tier |
| `.github/workflows/ci.yml`, test-health `contract.json`, `scan.py` | Citations point at real sections; `scan.py` refuses Python < 3.12 |

## 5. Testing
Unit: 78 planted-defect tests in `tests/unit/scripts/rule_integrity/`; four of them fail against the pre-fix checker (role directive, colon with no list, colon before a fence, renamed invariants heading). Architecture: the real-tree guard passes.

## Implementation notes (written when done)
Delivered in pull request PR 3. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
