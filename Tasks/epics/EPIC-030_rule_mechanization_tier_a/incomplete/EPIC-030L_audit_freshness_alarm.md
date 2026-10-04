# EPIC-030L — A silent scheduled audit raises an alarm

**Status:** 🔵 Backlog
**Source:** the user, 2026-10-04 — "gọn lại, bỏ J và K, làm B1 trước, nhiều task trong 1 PR nếu có thể, tui muốn đẩy thật nhanh epic này" (compact it, drop J and K, do B1 first, several tasks per PR, push this epic fast), after the audit "Sagittarius Rule Audit" of the same day.
**Risk:** 🟡 — A new workflow with `issues: write`, approved by the user
**Complexity:** S — delivered in PR 3
**Epic:** [EPIC-030](../README.md)
**Depends on:** None

---

## 1. Context and problem
`ONBOARDING.md` §13 says silence is never success, yet test-health last reported on 2026-09-07 and process-drift has never reported; nothing noticed.

## 2. Acceptance criteria
- [ ] A daily workflow opens or updates one labelled issue when the newest report of either audit is older than seven days.
- [ ] The freshness logic is a pure function tested with an injected date; no test reads the real clock.

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
