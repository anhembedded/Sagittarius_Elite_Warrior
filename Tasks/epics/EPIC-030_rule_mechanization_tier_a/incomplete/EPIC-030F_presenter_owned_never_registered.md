# EPIC-030F — Presenter-owned objects are never registered in the container

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — None
**Complexity:** S — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030C

---

## 1. Context and problem
`async-ui-action-rule.md` §2 and `domain-truth-rule.md` keep coordinators and the chart host presenter-owned; the only enforcement was an unwired grep that also matched the app-wide `UiStateCoordinator` (`app_bootstrapper.py:242`).

## 2. Acceptance criteria
- [ ] An AST guard flags a `singleton`/`bind`/`scoped` call naming a class defined in a presenter, coordinator or chart-host file, and does not flag `UiStateCoordinator`.

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
