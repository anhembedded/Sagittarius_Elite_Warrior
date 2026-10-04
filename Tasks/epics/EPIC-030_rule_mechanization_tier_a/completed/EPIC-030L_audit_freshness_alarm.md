# EPIC-030L — A silent scheduled audit raises an alarm

**Status:** ✅ Done (2026-10-04)
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟡 — A new workflow with `issues: write`, approved by the user
**Complexity:** S — delivered in PR 3
**Epic:** [EPIC-030](../README.md)
**Depends on:** None

---

## 1. Context and problem
`ONBOARDING.md` §13 says silence is never success, yet test-health last reported on 2026-09-07 and process-drift has never reported; nothing noticed.

## 2. Acceptance criteria
- [x] A daily workflow opens or updates one labelled issue when the newest report of either audit is older than seven days.
- [x] The freshness logic is a pure function tested with an injected date; no test reads the real clock.

## 3. Design
The design is recorded in the epic README §1 and in this task's pull request; the guard, where there is one, carries probe tests that prove it can fail.

## 4. Changes, per file
| File | Change |
| :--- | :--- |
| `scripts/check_audit_freshness.py`, `tests/unit/scripts/test_check_audit_freshness.py` | Pure freshness check with an injected date |
| `.github/workflows/audit-freshness.yml` | Daily run that opens or updates one `audit-stale` issue |

## 5. Testing
Unit tests with an injected date; the workflow YAML parses.

## Implementation notes (written when done)
Delivered in pull request #323. Verification: the GitHub Actions `ci-local.ps1 -Full` run on each pull request head, read from its job log by the author and by an independent reviewer session per code pull request; `python3 scripts/check_skill_prompt_references.py` reports no problem over 43 prompt documents on the final tree.
