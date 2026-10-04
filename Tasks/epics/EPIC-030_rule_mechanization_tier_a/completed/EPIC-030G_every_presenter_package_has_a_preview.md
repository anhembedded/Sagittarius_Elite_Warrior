# EPIC-030G — Every presenter package keeps a preview

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — None
**Complexity:** S — delivered in PR 2
**Epic:** [EPIC-030](../README.md)
**Depends on:** None

---

## 1. Context and problem
`tests/unit/presentation/ui/test_preview_fixtures_exist.py:27` scanned the deleted `src/presentation/ui/screens` and fell back to an empty list, so only the sidebar was checked.

## 2. Acceptance criteria
- [x] A guard over `modules/*/ui/**` and `shell/**` fails on a presenter package without `preview.py`, with a shrink-only baseline of today's gaps; a missing root fails.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/test_every_presenter_package_has_a_preview.py`, `baseline_presenter_packages_without_preview.txt` | New guard, four-entry shrink-only baseline |
| `tests/unit/presentation/ui/test_preview_fixtures_exist.py`, `scripts/preview_qml.py` | Static half moved to the guard; a missing root is an error |

## 5. Testing
Architecture guard; removing a preview, a stale baseline line or a relative import each turns one test red.

## Implementation notes (written when done)
Delivered in pull request #323. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
