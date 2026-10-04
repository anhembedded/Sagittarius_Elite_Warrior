# EPIC-030I — No runtime artifact is tracked

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟢 — None
**Complexity:** S — delivered in PR 3
**Epic:** [EPIC-030](../README.md)
**Depends on:** None

---

## 1. Context and problem
`commit-rule.md` §3 forbids committing `*.db`, `logs/`, `state/` and `.venv`; nothing checked the git index.

## 2. Acceptance criteria
- [x] A guard over the git index fails on a root-level `state/`, `logs/`, `database/`, `.venv/` path or a `.db`/`.sqlite` file, and not on `src/**/state/` or `src/**/database/` packages.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `tests/unit/architecture/test_no_runtime_artifact_is_tracked.py` | New guard over the git index |

## 5. Testing
Architecture guard; force-adding `state/ui_state.json` turns it red.

## Implementation notes (written when done)
Delivered in pull request #323. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
