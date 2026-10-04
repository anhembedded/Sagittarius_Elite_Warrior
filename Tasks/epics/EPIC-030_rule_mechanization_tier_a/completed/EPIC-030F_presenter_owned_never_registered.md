# EPIC-030F — Presenter-owned objects are never registered in the container

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — None
**Complexity:** S — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** EPIC-030C

---

## 1. Context and problem
`async-ui-action-rule.md` §2 and `domain-truth-rule.md` keep coordinators and the chart host presenter-owned; the only enforcement was an unwired grep that also matched the app-wide `UiStateCoordinator` (`app_bootstrapper.py:242`).

## 2. Acceptance criteria
- [x] An AST guard flags a `singleton`/`bind`/`scoped` call naming a class defined in a presenter, coordinator or chart-host file, and does not flag `UiStateCoordinator`.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/test_presenter_owned_objects_are_never_registered.py` | New AST guard keyed on where a class is defined |

## 5. Testing
Architecture guard plus probes; a planted registration turns it red; `UiStateCoordinator` is not flagged.

## Implementation notes (written when done)
Delivered in pull request #323. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
