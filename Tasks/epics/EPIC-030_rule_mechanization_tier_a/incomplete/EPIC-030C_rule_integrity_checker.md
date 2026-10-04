# EPIC-030C — The rule tree checks itself: tags, targets, sections, quotations, history

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟡 — A false positive blocks every commit
**Complexity:** M — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030A, EPIC-030B merged

---

## 1. Context and problem
`scripts/check_skill_prompt_references.py` verified paths and review IDs only. Section anchors, quotations, guard targets, gate claims and clause tags were checked by nobody, which is how every finding of `EPIC-030A` and `EPIC-030B` accumulated (the 2026-09-16 strategic review's PCS-5, still open).

## 2. Acceptance criteria
- [ ] `python3 scripts/check_skill_prompt_references.py` fails, with `file:line`, on an untagged clause, a missing or ambiguous guard, an unselected ruff gate, a missing section anchor, a malformed `§`, an out-of-range invariant, an invented quotation and a dated amendment.
- [ ] It passes on `master-warrior` after PR 1, on Python 3.11 and 3.12.
- [ ] A real-tree guard under `tests/unit/architecture` runs every check.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| Pending | Written when done. |

## 5. Testing
Not run. Each criterion maps to a unit test or guard under `tests/unit/`; documentation-only work names `python3 scripts/check_skill_prompt_references.py` and the document guards.

## Implementation notes (written when done)
Not yet established.
